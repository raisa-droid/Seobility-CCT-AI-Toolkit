#!/usr/bin/env bash
# refresh_aeo.sh
# AEO set for /refresh-analyze Step 4: Gemini grounded search (via the webhook,
# tools: [{googleSearch:{}}]) on the 3 phrasings built from the primary keyword,
# each run several times in parallel. Gemini's citation links are redirect URLs;
# they're resolved to the real pages. Pages are ranked by how often they're cited.
# Usage: ./scripts/refresh_aeo.sh "post URL" "phrasing 1" "phrasing 2" "phrasing 3"
# The post URL only names the cache folder. RUNS env var overrides runs per phrasing.
#
# Why 5 runs per phrasing (15 calls): tested 2026-09-30, 5 runs of the same
# question each cited 11-20 sites with little overlap between runs. With 3 runs
# per phrasing the top 3 changed on every repeat (4 repeats); with 5 runs it was
# identical on all 3 repeats. Pages are ranked across all runs:
#   1. cited in more phrasings (of 3)
#   2. cited in more runs (of phrasings × runs)
#   3. more answer sentences supported (groundingSupports)
#
# Gemini gets today's date as a system instruction, like real AI search has.
# Without it, Gemini 2.5 Flash searched for "2023" results.
#
# Returns JSON:
#   { data_available, runs_per_phrasing, calls, failed_calls,
#     phrasings: [{ text, runs_ok, search_queries: [...] }],
#     aeo_top3: [{ url, domain, phrasings_citing, runs_citing, supports }],
#     aeo_backups: [...],                        # next eligible pages, for swaps at Stop 2
#     aeo_skipped: [{ url, reason, phrasings_citing, runs_citing }] }
#
# Skip rules: same as refresh_serp.sh (Reddit, YouTube, Quora, forums,
# seobility.net, homepages, category/tag/archive pages). Links that don't resolve
# are skipped as "unresolved".
#
# Raw responses: .refresh-cache/<slug>/aeo_raw_<phrasing>_<run>.json.
# Parsed: aeo.json. Answers (for reading what AI search says): aeo_answers.json.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -f "$REPO/.env" ]; then
  source "$REPO/.env"
fi
source "$REPO/scripts/_api.sh"
require_gemini

# ── Input ──────────────────────────────────────────────────────────────────────
if [ $# -ne 4 ] || [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ]; then
  echo '{"data_available": false, "error": "Usage: refresh_aeo.sh \"post URL\" \"phrasing 1\" \"phrasing 2\" \"phrasing 3\""}' >&2
  exit 1
fi

SLUG=$(echo "$1" | sed -E 's#[?#].*$##; s#/+$##; s#.*/##')
PHRASINGS=("$2" "$3" "$4")
RUNS="${RUNS:-5}"
CACHE_DIR="$REPO/.refresh-cache/$SLUG"
mkdir -p "$CACHE_DIR"
rm -f "$CACHE_DIR"/aeo_raw_*.json

SYSTEM="Today's date is $(date +%Y-%m-%d)."

# ── Calls: phrasings × runs, in parallel ──────────────────────────────────────
for p in 1 2 3; do
  BODY=$(jq -n --arg prompt "${PHRASINGS[$((p - 1))]}" --arg sys "$SYSTEM" \
    '{systemInstruction: {parts: [{text: $sys}]}, contents: [{parts: [{text: $prompt}]}], tools: [{googleSearch: {}}]}')
  for r in $(seq 1 "$RUNS"); do
    ( gemini_post "$BODY" > "$CACHE_DIR/aeo_raw_${p}_${r}.json" \
      || echo '{"candidates": [], "error": "transport_failure"}' > "$CACHE_DIR/aeo_raw_${p}_${r}.json" ) &
  done
done
wait

# ── Resolve redirect links ────────────────────────────────────────────────────
# One request per unique link, no body download; the 302 Location is the page.
RAW_FILES=$(ls "$CACHE_DIR"/aeo_raw_*.json)
RESOLVED=$(jq -r '.candidates[0].groundingMetadata.groundingChunks[]?.web.uri // empty' $RAW_FILES 2>/dev/null \
  | sort -u \
  | xargs -P 10 -n 1 sh -c 'printf "%s\t%s\n" "$1" "$(curl -s -o /dev/null --max-time 15 -w "%{redirect_url}" "$1")"' _ \
  | jq -R -s 'split("\n") | map(select(length > 0) | split("\t") | {key: .[0], value: (.[1] // "")}) | from_entries')

# ── Parse ──────────────────────────────────────────────────────────────────────
# Each raw file is tagged with its phrasing number from the file name.
for f in $RAW_FILES; do
  p=$(basename "$f" | sed -E 's/aeo_raw_([0-9]+)_[0-9]+\.json/\1/')
  jq -c --argjson p "$p" '{p: $p, resp: .}' "$f" 2>/dev/null || jq -n -c --argjson p "$p" '{p: $p, resp: {}}'
done | jq -s \
  --argjson resolved "$RESOLVED" \
  --argjson runs "$RUNS" \
  --arg p1 "${PHRASINGS[0]}" --arg p2 "${PHRASINGS[1]}" --arg p3 "${PHRASINGS[2]}" \
  --arg answers_file "$CACHE_DIR/aeo_answers.json" '
  def norm_url: ascii_downcase | sub("^https?://"; "") | sub("^www\\."; "") | sub("[?#].*$"; "") | sub("/+$"; "");
  def host: norm_url | split("/")[0];
  def path: norm_url | (split("/")[1:] | join("/"));
  def skip_reason:
    (.url | host) as $h | (.url | path) as $p |
    if ($h | test("(^|\\.)reddit\\.com$")) then "reddit"
    elif ($h | test("(^|\\.)(youtube\\.com|youtu\\.be)$")) then "youtube"
    elif ($h | test("(^|\\.)quora\\.com$")) then "quora"
    elif ($h | test("(^|\\.)seobility\\.net$")) then "seobility"
    elif ($h | test("(^|\\.)(stackexchange\\.com|stackoverflow\\.com)$|^(forum|forums|community|discuss)\\.")
          or ($p | test("(^|/)(forum|forums|community|threads?|discussions?)(/|$)"))) then "forum"
    elif $p == "" or ($p | test("^[a-z]{2}(-[a-z]{2})?$")) then "homepage"
    elif ($p | test("(^|/)(category|categories|tag|tags|topics?|archive|author|c|page)(/|$)")) then "category or archive page"
    else null end;

  [$p1, $p2, $p3] as $texts |
  map(. + {ok: ((.resp.candidates // []) | length > 0)}) as $calls |
  ($calls | map(select(.ok))) as $ok |

  # One row per (run, cited page): resolved URL + how many answer sentences it supports.
  [ $ok | to_entries[] | .key as $run | .value as $c |
    ($c.resp.candidates[0].groundingMetadata // {}) as $gm |
    ($gm.groundingChunks // []) | to_entries[] |
    .key as $i | .value.web as $w |
    ($resolved[$w.uri] // "") as $u |
    { run: $run, p: $c.p,
      url: (if $u == "" then null else ($u | sub("#.*$"; "")) end),
      domain: ($w.title // null),
      supports: ([$gm.groundingSupports[]? | select(.groundingChunkIndices | index($i))] | length) }
  ] as $cites |

  # Aggregate per page.
  ($cites | map(select(.url != null)) | group_by(.url | norm_url) | map({
      url: .[0].url,
      domain: (.[0].url | host),
      phrasings_citing: (map(.p) | unique | length),
      runs_citing: (map(.run) | unique | length),
      supports: (map(.supports) | add)
    }) | sort_by([-.phrasings_citing, -.runs_citing, -.supports])
  ) as $pages |
  ($pages | map(. + {reason: skip_reason})) as $tagged |
  ($tagged | map(select(.reason == null) | del(.reason))) as $eligible |
  ($cites | map(select(.url == null)) | length) as $unresolved |

  {
    data_available: (($ok | length) > 0),
    runs_per_phrasing: $runs,
    calls: ($calls | length),
    failed_calls: (($calls | length) - ($ok | length)),
    unresolved_links: $unresolved,
    phrasings: [range(1; 4) as $n | {
      text: $texts[$n - 1],
      runs_ok: ($ok | map(select(.p == $n)) | length),
      search_queries: ($ok | map(select(.p == $n) | .resp.candidates[0].groundingMetadata.webSearchQueries // []) | add // [] | unique)
    }],
    aeo_top3: $eligible[0:3],
    aeo_backups: $eligible[3:8],
    aeo_skipped: ($tagged | map(select(.reason != null)) | map({url, reason, phrasings_citing, runs_citing})),
    answers: [$ok[] | {phrasing: .p, text: (.resp.candidates[0].content.parts // [] | map(.text // "") | join(""))}]
  }
' > "$CACHE_DIR/aeo_full.json"

# Answers go to their own file; stdout and aeo.json get everything else.
jq '.answers' "$CACHE_DIR/aeo_full.json" > "$CACHE_DIR/aeo_answers.json"
jq 'del(.answers)' "$CACHE_DIR/aeo_full.json" | tee "$CACHE_DIR/aeo.json"
rm -f "$CACHE_DIR/aeo_full.json"

#!/usr/bin/env bash
# refresh_serp.sh
# SEO set for /refresh-analyze Step 4: DataForSEO SERP (organic live advanced,
# US English, depth 10) for the primary keyword, called 7 times in parallel,
# plus one stored-snapshot call that picks which live result set is real.
# Usage: ./scripts/refresh_serp.sh "primary kw" "https://www.seobility.net/en/blog/post-slug/"
# The post URL names the cache folder and is matched to find our rank.
#
# Why 7 calls (tested 2026-09-30, 105 calls over 3 keywords): about half of all
# live calls return a different, weaker result set for the same keyword seconds
# apart, sharing 0-1 of their top 10 with the real set. Bad calls come in streaks.
# In 15 batches, the first 5 calls missed the real set once; 7 calls never did.
# Calls are grouped by top-10 overlap (same set = at least 5 shared URLs).
#
# Tiebreaker: DataForSEO Labs historical SERPs (stored Google snapshots, weeks or
# months old, $0.0005). Too old to use as the competitor list, but every tested
# snapshot matched the real set (4-8 of 10 shared) and never the bad one (0-1).
# The live set sharing the most URLs with the latest snapshot (at least 3) is
# recommended. No majority vote: the bad set was the majority in 3 of 4 early runs.
#   - No live set matches the snapshot: 7 more calls, once. Still none: no_match.
#   - No stored snapshot for this keyword: no_snapshot, Claude judges at Stop 2.
#
# Returns JSON:
#   { data_available, keyword, calls, failed_calls, retried: bool,
#     snapshot: { available, date },
#     recommendation_basis: "snapshot" | "no_match" | "no_snapshot",
#     recommended_set: 0 | null,                 # index into sets
#     sets: [{                                   # recommended first, then largest
#       calls: [1, 3, 4],                        # which calls returned this set
#       snapshot_overlap: 6 | null,              # top-10 URLs shared with the snapshot
#       our_rank: 4 | null,                      # best organic rank of our post across these calls
#       tier: "protect" | "striking_distance" | "needs_content",
#       organic_top3: [{ rank, title, url, domain }],
#       organic_backups: [...],                  # remaining eligible results, for swaps at Stop 2
#       organic_skipped: [{ rank, url, reason }],
#       ai_overview: { present, seobility_cited, sources: [{ title, url, domain }] },
#       paa_present, paa_questions: [...], related_searches: [...]
#     }] }
#
# Skip rules (by URL): Reddit, YouTube, Quora, forums/communities, seobility.net,
# homepages, category/tag/archive pages. Pages that aren't articles but have
# normal-looking URLs (tool pages, dashboards) are for Claude to catch at Stop 2.
#
# Tier (internal only, never shown to users; it steers priorities, see design doc
# "Performance tier"): rank 1–3 protect, 4–10 striking_distance, 11+ or not found
# needs_content. Depth 10 is enough to tell them apart.
#
# Cost: $0.002 per live call (depth 10 costs the same as depth 5) + $0.0005
# snapshot = ~$0.015 per run, ~$0.03 with the retry. ~20 seconds (~40 with retry).
# load_async_ai_overview is on (no extra cost) to catch late-loading AI Overviews.
# Raw responses: .refresh-cache/<slug>/serp_raw_<n>.json, serp_snapshot_raw.json.
# Parsed: serp.json.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -f "$REPO/.env" ]; then
  source "$REPO/.env"
fi
source "$REPO/scripts/_api.sh"
require_dfs

# ── Input ──────────────────────────────────────────────────────────────────────
if [ $# -lt 2 ] || [ -z "$1" ] || [ -z "$2" ]; then
  echo '{"data_available": false, "error": "Usage: refresh_serp.sh \"primary kw\" \"post URL\""}' >&2
  exit 1
fi

KEYWORD="$1"
OUR_URL="$2"
SLUG=$(echo "$2" | sed -E 's#[?#].*$##; s#/+$##; s#.*/##')
CACHE_DIR="$REPO/.refresh-cache/$SLUG"
mkdir -p "$CACHE_DIR"

# ── Calls ────────────────────────────────────────────────────────────────────
BODY=$(jq -n \
  --arg kw "$KEYWORD" \
  '[{"keyword": $kw, "location_code": 2840, "language_code": "en", "depth": 10, "load_async_ai_overview": true}]')
PAYLOAD=$(jq -n --arg endpoint 'https://api.dataforseo.com/v3/serp/google/organic/live/advanced' --argjson body "$BODY" '{endpoint: $endpoint, body: $body}')

SNAP_BODY=$(jq -n \
  --arg kw "$KEYWORD" \
  '[{"keyword": $kw, "location_code": 2840, "language_code": "en"}]')
SNAP_PAYLOAD=$(jq -n --arg endpoint 'https://api.dataforseo.com/v3/dataforseo_labs/google/historical_serps/live' --argjson body "$SNAP_BODY" '{endpoint: $endpoint, body: $body}')

BATCH=7

# live_calls FIRST LAST: live SERP calls FIRST..LAST in parallel.
live_calls() {
  for i in $(seq "$1" "$2"); do
    dfs_post "$PAYLOAD" > "$CACHE_DIR/serp_raw_$i.json" &
  done
  wait
}

rm -f "$CACHE_DIR"/serp_raw_*.json "$CACHE_DIR/serp_snapshot_raw.json"
dfs_post "$SNAP_PAYLOAD" > "$CACHE_DIR/serp_snapshot_raw.json" &
live_calls 1 $BATCH

# ── Parse ──────────────────────────────────────────────────────────────────────
# parse N RETRIED: parse live calls 1..N against the snapshot.
parse() {
jq -s \
  --arg kw "$KEYWORD" \
  --arg our_url "$OUR_URL" \
  --argjson retried "$2" \
  --slurpfile snap "$CACHE_DIR/serp_snapshot_raw.json" '
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

  def tier($r):
    if $r == null or $r > 10 then "needs_content"
    elif $r <= 3 then "protect"
    else "striking_distance" end;

  def shared($a; $b): [$a[] | select(. as $u | $b | index($u))] | length;

  # Latest stored snapshot: its top-10 organic URLs, or null if there is none.
  ($snap[0].tasks[0]? | select(.status_code == 20000) | .result[0].items // []
    | sort_by(.datetime) | last) as $latest |
  ($latest | if . == null then null
             else [.items[]? | select(.type == "organic") | .url | norm_url][0:10] end) as $snap_top10 |

  # One call → parsed set, or null if the call failed.
  def parse($n):
    .tasks[0]? |
    if . == null or .status_code != 20000 or ((.result[0].items // []) | length) == 0 then null else
    .result[0].items as $items |

    ($items | map(select(.type == "organic")) | map({rank: .rank_group, title, url, domain})) as $organic |
    ($organic | map(. + {reason: skip_reason})) as $tagged |
    ($tagged | map(select(.reason == null) | del(.reason))) as $eligible |

    # AI Overview sources: top-level references plus any nested in its items. Deduped by URL.
    ($items | map(select(.type == "ai_overview")) | first) as $aio |
    ([$aio.references[]?, ($aio.items[]? | .references[]?)]
      | map(select(.url != null) | {title, url, domain})
      | reduce .[] as $r ([]; if any(.[]; (.url | norm_url) == ($r.url | norm_url)) then . else . + [$r] end)
    ) as $aio_sources |

    ($items | map(select(.type == "people_also_ask")) | first) as $paa |
    ($items | map(select(.type == "related_searches")) | map(.items[]?)
      | reduce .[] as $s ([]; if any(.[]; ascii_downcase == ($s | ascii_downcase)) then . else . + [$s] end)
    ) as $related |

    ($organic | map(select((.url | norm_url) == ($our_url | norm_url))) | first | .rank) as $our_rank |

    ($organic | map(.url | norm_url)) as $top10 |

    {
      calls: [$n],
      snapshot_overlap: (if $snap_top10 then shared($top10; $snap_top10) else null end),
      our_rank: $our_rank,
      top10: $top10,
      organic_top3: $eligible[0:3],
      organic_backups: $eligible[3:],
      organic_skipped: ($tagged | map(select(.reason != null)) | map({rank, url, reason})),
      ai_overview: {
        present: ($aio != null),
        seobility_cited: ($aio_sources | any(.url | host | test("(^|\\.)seobility\\.net$"))),
        sources: $aio_sources
      },
      paa_present: ($paa != null),
      paa_questions: (if $paa then [$paa.items[]?.title | select(. != null)] else [] end),
      related_searches: $related
    } end;

  [range(0; length) as $i | .[$i] | parse($i + 1)] as $all |
  ($all | map(select(. != null))) as $parsed |
  if ($parsed | length) == 0 then
    error("All \($all | length) SERP calls failed or returned no results. First status: \(.[0].tasks[0]?.status_message // "no response")")
  else . end |

  # Group calls whose top 10 share at least 5 URLs. The first call in a group
  # represents it; its PAA and AI Overview are the ones reported.
  (reduce $parsed[] as $p ([];
    (map(shared(.top10; $p.top10) >= 5) | index(true)) as $g |
    if $g == null then . + [$p]
    else .[$g].calls += $p.calls
         | .[$g].our_rank = ([.[$g].our_rank, $p.our_rank] | map(select(. != null)) | min)
         | .[$g].snapshot_overlap = ([.[$g].snapshot_overlap, $p.snapshot_overlap] | map(select(. != null)) | max)
    end
  )) as $groups |

  # Recommended first (most snapshot overlap, at least 3), then by number of calls.
  ($groups | map(.tier = tier(.our_rank) | del(.top10))
    | sort_by([-(.snapshot_overlap // -1), -(.calls | length)])) as $sets |
  ($snap_top10 != null and ($sets[0].snapshot_overlap // 0) >= 3) as $matched |

  {
    data_available: true,
    keyword: $kw,
    calls: ($all | length),
    failed_calls: (($all | length) - ($parsed | length)),
    retried: $retried,
    snapshot: {available: ($snap_top10 != null), date: ($latest.datetime? // null | if . then .[0:10] else null end)},
    recommendation_basis: (if $snap_top10 == null then "no_snapshot" elif $matched then "snapshot" else "no_match" end),
    recommended_set: (if $matched then 0 else null end),
    sets: (if $snap_top10 == null or ($matched | not) then ($sets | sort_by(-(.calls | length))) else $sets end)
  }
' $(for i in $(seq 1 "$1"); do echo "$CACHE_DIR/serp_raw_$i.json"; done)
}

RESULT=$(parse $BATCH false)

# No live set matched the snapshot: the real set may not have shown up. Retry once.
if [ "$(echo "$RESULT" | jq -r .recommendation_basis)" = "no_match" ]; then
  live_calls $((BATCH + 1)) $((BATCH * 2))
  RESULT=$(parse $((BATCH * 2)) true)
fi

echo "$RESULT" | tee "$CACHE_DIR/serp.json"

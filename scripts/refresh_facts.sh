#!/usr/bin/env bash
# refresh_facts.sh
# Third-party fact check for /refresh-analyze Step 8: each claim Claude pulled
# from the post is checked with grounded Gemini (via the webhook) against live
# sources. Seobility pricing and features are NOT checked here: Claude checks
# those against product-context/ directly.
# Usage: ./scripts/refresh_facts.sh "post URL" claims.json
# The post URL only names the cache folder. RUNS env var overrides runs per claim.
#
# claims.json: [{ "id": "C1", "block": "P38", "claim": "exact claim text",
#                 "entity": "Google PageSpeed Insights",
#                 "kind": "pricing" | "feature" | "spec" | "stat" | "reference" | "definition" }]
#
# Gemini only searches and reports; Claude judges. Rules sent with every claim:
# expand inherited tiers ("Everything in Starter, plus X"), never mix monthly
# and annual prices, match currencies, prefer the official/primary source, and
# say "unverifiable" instead of guessing.
#
# Verdict per claim (across runs):
#   correct            every deciding run says correct
#   outdated / wrong   every deciding run says the claim needs a fix (wrong and
#                      outdated agree with each other; the more common one is used)
#   disputed           some runs say correct, others say it needs a fix
#                      → becomes [TODO · VERIFY: …]
#   unverifiable       every run said unverifiable, or no run cited a live source
# "Deciding" runs exclude runs that answered unverifiable.
# Sources are taken from Gemini's grounding metadata (real search results,
# redirects resolved), not from URLs Gemini writes in its answer.
#
# Returns JSON:
#   { data_available, runs_per_claim, calls, failed_calls,
#     claims: [{ id, block, claim, entity, kind, verdict,
#                current_fact, correction, runs: [{verdict, current_fact, correction, notes}],
#                sources: [url] }] }
#
# Raw responses: .refresh-cache/<slug>/facts_raw_<id>_<run>.json. Parsed: facts.json.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -f "$REPO/.env" ]; then
  source "$REPO/.env"
fi
source "$REPO/scripts/_api.sh"
require_gemini

# ── Input ──────────────────────────────────────────────────────────────────────
if [ $# -ne 2 ] || [ ! -f "$2" ] || ! jq -e 'type == "array" and length > 0' "$2" >/dev/null 2>&1; then
  echo '{"data_available": false, "error": "Usage: refresh_facts.sh \"post URL\" claims.json (a non-empty JSON array)"}' >&2
  exit 1
fi

SLUG=$(echo "$1" | sed -E 's#[?#].*$##; s#/+$##; s#.*/##')
CLAIMS_FILE="$2"
RUNS="${RUNS:-2}"
CACHE_DIR="$REPO/.refresh-cache/$SLUG"
mkdir -p "$CACHE_DIR"
rm -f "$CACHE_DIR"/facts_raw_*.json

TODAY=$(date +%Y-%m-%d)
SYSTEM="Today's date is $TODAY. You are a fact checker. You search the web and report what current sources say. You never guess."

# ── Calls: claims × runs, in parallel ─────────────────────────────────────────
N=$(jq 'length' "$CLAIMS_FILE")
for i in $(seq 0 $((N - 1))); do
  ID=$(jq -r ".[$i].id" "$CLAIMS_FILE")
  CLAIM=$(jq -r ".[$i].claim" "$CLAIMS_FILE")
  ENTITY=$(jq -r ".[$i].entity // \"unspecified\"" "$CLAIMS_FILE")
  KIND=$(jq -r ".[$i].kind // \"fact\"" "$CLAIMS_FILE")
  # read -d '' instead of $(cat <<EOF): macOS bash 3.2 misparses apostrophes in a
  # heredoc inside command substitution.
  read -r -d '' PROMPT <<EOF || true
Check this claim from a blog post against current, live sources.

Claim: "$CLAIM"
About: $ENTITY
Kind: $KIND

Rules:
- Search for the official or primary source first (the vendor's own pricing or docs page, the original study). Use secondary sources only if no primary source exists.
- Pricing: expand inherited tiers ("Everything in Starter, plus X" means Starter's full list plus X). Never mix monthly and annual prices; say which one a price is. Keep the currency of the claim, or say clearly that the source uses another one.
- Definition: check what the official documentation says the metric, tool or term measures or does, including its scope and its threshold. A definition that describes a different or older metric (or only part of what it covers) is wrong or outdated.
- If a fact was true once but has since changed, the verdict is outdated, and say what it is now.
- If you can't confirm it from a source you actually found, the verdict is unverifiable. Do not guess a correction.

Answer with a short explanation, then end with exactly one JSON block:
\`\`\`json
{"verdict": "correct | outdated | wrong | unverifiable", "current_fact": "what current sources say, one or two sentences", "correction": "corrected wording of the claim, or null if correct or unverifiable", "notes": "caveats: billing period, currency, plan names, source date"}
\`\`\`
EOF
  BODY=$(jq -n --arg prompt "$PROMPT" --arg sys "$SYSTEM" \
    '{systemInstruction: {parts: [{text: $sys}]}, contents: [{parts: [{text: $prompt}]}], tools: [{googleSearch: {}}]}')
  for r in $(seq 1 "$RUNS"); do
    ( gemini_post "$BODY" > "$CACHE_DIR/facts_raw_${ID}_${r}.json" \
      || echo '{"candidates": [], "error": "transport_failure"}' > "$CACHE_DIR/facts_raw_${ID}_${r}.json" ) &
  done
done
wait

# ── Resolve grounding redirect links ──────────────────────────────────────────
RAW_FILES=$(ls "$CACHE_DIR"/facts_raw_*.json)
RESOLVED=$(jq -r '.candidates[0].groundingMetadata.groundingChunks[]?.web.uri // empty' $RAW_FILES 2>/dev/null \
  | sort -u \
  | xargs -P 10 -n 1 sh -c 'printf "%s\t%s\n" "$1" "$(curl -s -o /dev/null --max-time 15 -w "%{redirect_url}" "$1")"' _ \
  | jq -R -s 'split("\n") | map(select(length > 0) | split("\t") | {key: .[0], value: (.[1] // "")}) | from_entries')

# ── Parse ──────────────────────────────────────────────────────────────────────
# Each raw file → {id, text (answer), json (last ```json block), sources}.
for f in $RAW_FILES; do
  id=$(basename "$f" | sed -E 's/facts_raw_(.+)_[0-9]+\.json/\1/')
  text=$(jq -r '(.candidates[0].content.parts // []) | map(.text // "") | join("")' "$f" 2>/dev/null || echo "")
  block=$(printf '%s\n' "$text" | awk '
    /```json/ { capture=1; buf=""; next }
    /```/ { if (capture) { capture=0; last=buf }; next }
    capture { buf = buf $0 "\n" }
    END { printf "%s", last }')
  if [ -z "$block" ] || ! printf '%s' "$block" | jq -e 'type == "object"' >/dev/null 2>&1; then
    block='null'
  fi
  jq -c -n --arg id "$id" --argjson parsed "$block" --argjson resolved "$RESOLVED" --slurpfile raw "$f" '
    {id: $id, parsed: $parsed,
     sources: [($raw[0].candidates[0].groundingMetadata.groundingChunks // [])[] | .web.uri
               | ($resolved[.] // "") | select(. != "") | sub("#.*$"; "")]}'
done | jq -s --slurpfile claims "$CLAIMS_FILE" --argjson runs "$RUNS" '
  . as $all |
  ($all | group_by(.id) | map({key: .[0].id, value: .}) | from_entries) as $by_id |
  ($claims[0] | map(
    . as $c |
    ($by_id[$c.id] // []) as $rs |
    ($rs | map(select(.parsed != null and (.parsed.verdict | type) == "string"))) as $ok |
    ($ok | map(.parsed.verdict | ascii_downcase | gsub("\\s"; ""))) as $vs |
    ($vs | map(select(. != "unverifiable"))) as $decided |
    ($decided | map(select(. == "wrong" or . == "outdated"))) as $fix |
    ($rs | map(.sources[]) | unique) as $sources |
    # wrong and outdated both mean "needs a fix", so they agree with each other.
    # Unverifiable runs are ignored unless every run is unverifiable.
    (if ($decided | length) == 0 then "unverifiable"
     elif ($fix | length) > 0 and ($fix | length) < ($decided | length) then "disputed"
     elif ($sources | length) == 0 then "unverifiable"
     elif ($fix | length) == 0 then "correct"
     elif ($fix | map(select(. == "outdated")) | length) * 2 > ($fix | length) then "outdated"
     else "wrong" end) as $verdict |
    $c + {
      verdict: $verdict,
      current_fact: ($ok | map(.parsed.current_fact) | map(select(. != null and . != "")) | first // null),
      correction: (if $verdict == "outdated" or $verdict == "wrong"
                   then ($ok | map(.parsed.correction) | map(select(. != null and . != "" and . != "null")) | first // null)
                   else null end),
      runs: ($rs | map(.parsed // {verdict: "no_answer"} | {verdict, current_fact, correction, notes})),
      sources: $sources
    }
  )) as $out |
  {
    data_available: true,
    runs_per_claim: $runs,
    calls: ($all | length),
    failed_calls: ($all | map(select(.parsed == null)) | length),
    claims: $out
  }
' > "$CACHE_DIR/facts.json"

# Short summary: what needs attention in full, confirmed claims in one line.
# The full results (every run, every source) are in facts.json.
jq -r '
  def cut($n): if . == null then "" else (tostring | if length > $n then .[0:$n-1] + "…" else . end) end;
  "FACTS: \(.claims | length) claims checked (\(.runs_per_claim) runs each, \(.failed_calls) failed calls) | " +
    ([.claims | group_by(.verdict)[] | "\(.[0].verdict) \(length)"] | join(", ")),
  (.claims[] | select(.verdict != "correct") |
    " \(.id) [\(.block)] \(.verdict) | claim: \(.claim | cut(150))",
    "   now: \(.current_fact | cut(280))",
    (if .correction then "   fix: \(.correction | cut(280))" else empty end),
    "   sources: \(.sources[0:3] | join(", "))"),
  (if ([.claims[] | select(.verdict == "correct")] | length) > 0
   then " confirmed: " + ([.claims[] | select(.verdict == "correct") | "\(.id) (\(.sources | length) sources)"] | join(", "))
   else empty end),
  " full results: .refresh-cache/'"$SLUG"'/facts.json"
' "$CACHE_DIR/facts.json"

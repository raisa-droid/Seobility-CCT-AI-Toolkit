#!/usr/bin/env bash
# brief_dataforseo.sh
# Replicates: ACTIVE_Seobility_Brief — KW Overview Webhook
# Usage: ./brief_kw_overview.sh "keyword one" "keyword two" "keyword three"
# Returns JSON: { data_available, results: [{keyword, sv, intent}] }
# Max 15 keywords. Filtering by SV threshold is Claude's job.

set -euo pipefail

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -f "$(dirname "$0")/../.env" ]; then
  source "$(dirname "$0")/../.env"
fi

: "${DATAFORSEO_WEBHOOK_URL:?DATAFORSEO_WEBHOOK_URL not set}"

# ── Input ──────────────────────────────────────────────────────────────────────
if [ $# -eq 0 ]; then
  echo '{"data_available": false, "error": "No keywords provided"}' >&2
  exit 1
fi

if [ $# -gt 15 ]; then
  echo '{"data_available": false, "error": "Max 15 keywords allowed"}' >&2
  exit 1
fi

# Build JSON array from arguments
KEYWORDS_ARRAY=$(printf '%s\n' "$@" | jq -R . | jq -s .)

# ── Call: keyword_overview ─────────────────────────────────────────────────────
BODY=$(jq -n \
  --argjson kws "$KEYWORDS_ARRAY" \
  '[{"keywords": $kws, "location_code": 2840, "language_code": "en"}]')

RESPONSE=$(curl -s -X POST \
  "${DATAFORSEO_WEBHOOK_URL}" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg endpoint 'https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_overview/live' --argjson body "$BODY" '{endpoint: $endpoint, body: $body}')")

# ── Parse ──────────────────────────────────────────────────────────────────────
echo "$RESPONSE" | jq \
  --argjson input_kws "$KEYWORDS_ARRAY" '
  .tasks[0] |
  if .status_code != 20000 then
    error("Keyword Overview failed: \(.status_message)")
  else . end |
  .result[0].items |
  if (. == null or length == 0) then error("Keyword Overview returned no items") else . end |

  # Build result map (lowercase for case-insensitive match)
  (reduce .[] as $item (
    {};
    (.[$item.keyword | ascii_downcase]) = {
      sv: ($item.keyword_info.search_volume // null),
      intent: ($item.search_intent_info.main_intent // null)
    }
  )) as $result_map |

  {
    data_available: true,
    results: ($input_kws | map({
      keyword: .,
      sv: ($result_map[ascii_downcase] // {sv: null}).sv,
      intent: ($result_map[ascii_downcase] // {intent: null}).intent
    }))
  }
'

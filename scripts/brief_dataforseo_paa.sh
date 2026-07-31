#!/usr/bin/env bash
# brief_dataforseo_paa.sh
# Fetches People Also Ask questions for a given query via DataforSEO SERP endpoint.
# Usage: ./brief_dataforseo_paa.sh "How to Do an SEO Audit"
# Returns JSON: { data_available, query, paa_present, questions: ["...", "..."] }
# depth: 20 — covers PAA appearing at any rank_absolute position up to 20.

set -euo pipefail

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -f "$(dirname "$0")/../.env" ]; then
  source "$(dirname "$0")/../.env"
fi

: "${DATAFORSEO_LOGIN:?DATAFORSEO_LOGIN not set}"
: "${DATAFORSEO_PASSWORD:?DATAFORSEO_PASSWORD not set}"

AUTH=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

# ── Input ──────────────────────────────────────────────────────────────────────
if [ $# -eq 0 ]; then
  echo '{"data_available": false, "error": "No query provided"}' >&2
  exit 1
fi

QUERY="$1"

# ── Call: SERP organic live advanced ──────────────────────────────────────────
BODY=$(jq -n \
  --arg query "$QUERY" \
  '[{"keyword": $query, "location_code": 2840, "language_code": "en", "depth": 20}]')

RESPONSE=$(curl -s -X POST \
  "https://api.dataforseo.com/v3/serp/google/organic/live/advanced" \
  -H "Authorization: Basic $AUTH" \
  -H "Content-Type: application/json" \
  -d "$BODY")

# ── Parse ──────────────────────────────────────────────────────────────────────
echo "$RESPONSE" | jq \
  --arg query "$QUERY" '
  .tasks[0] |
  if .status_code != 20000 then
    error("SERP request failed: \(.status_message)")
  else . end |
  .result[0].items as $items |
  if ($items == null or ($items | length) == 0) then
    error("SERP returned no items")
  else . end |

  # Find the people_also_ask block
  ($items | map(select(.type == "people_also_ask")) | first) as $paa_block |

  if $paa_block == null then
    {
      data_available: true,
      query: $query,
      paa_present: false,
      questions: []
    }
  else
    {
      data_available: true,
      query: $query,
      paa_present: true,
      questions: [$paa_block.items[].title]
    }
  end
'

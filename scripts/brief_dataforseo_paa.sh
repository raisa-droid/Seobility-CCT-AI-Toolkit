#!/usr/bin/env bash
# brief_dataforseo_paa.sh
# Fetches People Also Ask questions for a given query via DataforSEO SERP endpoint.
# Usage: ./brief_dataforseo_paa.sh "How to Do an SEO Audit"
# Returns JSON: { data_available, query, paa_present, questions: ["...", "..."], related_searches: ["...", "..."] }
# depth: 20 — covers PAA appearing at any rank_absolute position up to 20.
# related_searches is only populated when paa_present is false — it's a fallback
# source for FAQ generation, deduped and stripped of query-echo artifacts (items
# that are just the literal query plus a bolt-on word, e.g. "...checklist free").
# Filtering for topical/format/funnel fit and rephrasing into questions is a
# judgment call left to the brief skill, not done here.

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

  # Gather related_searches items (may appear in multiple blocks), dedupe
  # case-insensitively (first occurrence wins), and strip query-echo artifacts
  # (items that are just the literal query plus a bolt-on word).
  ($items | map(select(.type == "related_searches")) | map(.items[])) as $rs_all |
  ($rs_all | reduce .[] as $item ([];
    if any(.[]; ascii_downcase == ($item | ascii_downcase)) then .
    else . + [$item] end
  )) as $rs_deduped |
  (def norm: ascii_downcase | gsub("[^a-z0-9 ]"; " ") | gsub(" +"; " ") | ltrimstr(" ") | rtrimstr(" ");
   ($query | norm) as $qnorm |
   $rs_deduped | map(select((. | norm | startswith($qnorm)) | not))
  ) as $rs_filtered |

  if $paa_block == null then
    {
      data_available: true,
      query: $query,
      paa_present: false,
      questions: [],
      related_searches: $rs_filtered
    }
  else
    {
      data_available: true,
      query: $query,
      paa_present: true,
      questions: [$paa_block.items[].title],
      related_searches: []
    }
  end
'

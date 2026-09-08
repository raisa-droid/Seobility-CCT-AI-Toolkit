#!/usr/bin/env bash
# brief_gemini.sh
# Replicates: ACTIVE_Seobility_Brief — Gemini Webhook
# Usage: ./brief_gemini.sh "Your H1 title here"
# Returns JSON: { data_available, h1, synthesis, sources_raw }

set -euo pipefail

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -f "$(dirname "$0")/../.env" ]; then
  source "$(dirname "$0")/../.env"
fi

: "${GEMINI_WEBHOOK_URL:?GEMINI_WEBHOOK_URL not set}"

# ── Input ──────────────────────────────────────────────────────────────────────
H1="${1:-}"
if [ -z "$H1" ]; then
  echo '{"data_available": false, "error": "Missing h1 argument"}' >&2
  exit 1
fi

# ── Call: Gemini 2.5 Flash via n8n webhook ─────────────────────────────────────
PROMPT="${H1}. include your source list with specific article URLs, not homepages or domain names only."

BODY=$(jq -n --arg prompt "$PROMPT" \
  '{"contents": [{"parts": [{"text": $prompt}]}]}')

RESPONSE=$(curl -s -X POST \
  "${GEMINI_WEBHOOK_URL}" \
  -H "Content-Type: application/json" \
  -d "$BODY")

# ── Parse ──────────────────────────────────────────────────────────────────────
echo "$RESPONSE" | jq \
  --arg h1 "$H1" '
  .candidates[0].content.parts[0].text as $text |
  if ($text == null or ($text | length) == 0) then
    error("Gemini returned no text content")
  else . end |

  # Extract sources section — find first occurrence of known source headers
  ($text | ascii_downcase) as $lower |
  (["sources used:", "source list", "sources:", "references:", "further reading:"] |
    reduce .[] as $header (
      null;
      if . == null then
        ($lower | index($header)) as $idx |
        if $idx != null then $idx else null end
      else . end
    )
  ) as $source_idx |

  # Clean Google redirect URLs from sources
  ($text |
    if $source_idx != null then .[$source_idx:] else "No sources section found in Gemini response" end |
    gsub("https://www.google.com/search\\?q=https?%3A%2F%2F"; "https://") |
    gsub("https://www.google.com/search\\?q=https?://"; "https://")
  ) as $sources_raw |

  {
    data_available: true,
    h1: $h1,
    synthesis: $text,
    sources_raw: $sources_raw
  }
'

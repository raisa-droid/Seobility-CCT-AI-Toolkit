#!/usr/bin/env bash
# sera_dataforseo.sh
# Replicates: ACTIVE_Sera DataforSEO Webhook_SV 150
# Usage: ./sera_dataforseo.sh "technical seo"
# Returns JSON: { data_available, seed_kw, winner, all_variants, fallback_applied }

set -euo pipefail

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -f "$(dirname "$0")/../.env" ]; then
  source "$(dirname "$0")/../.env"
fi

: "${DATAFORSEO_LOGIN:?DATAFORSEO_LOGIN not set}"
: "${DATAFORSEO_PASSWORD:?DATAFORSEO_PASSWORD not set}"

AUTH=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

# ── Input ──────────────────────────────────────────────────────────────────────
SEED_KW="${1:-}"
if [ -z "$SEED_KW" ]; then
  echo '{"data_available": false, "error": "Missing seed_kw argument"}' >&2
  exit 1
fi

# ── Call 1: keyword_suggestions ───────────────────────────────────────────────
CALL1_BODY=$(jq -n \
  --arg kw "$SEED_KW" \
  '[{"keyword": $kw, "location_code": 2840, "language_code": "en", "limit": 20}]')

CALL1_RESPONSE=$(curl -s -X POST \
  "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_suggestions/live" \
  -H "Authorization: Basic $AUTH" \
  -H "Content-Type: application/json" \
  -d "$CALL1_BODY")

# Parse Call 1: filter SV >= 150, min 3 words, sort desc, top 20
VARIANTS=$(echo "$CALL1_RESPONSE" | jq --arg seed "$SEED_KW" '
  .tasks[0] |
  if .status_code != 20000 then
    error("Call 1 failed: \(.status_message)")
  else . end |
  .result[0].items |
  if (. == null or length == 0) then error("Call 1 returned no items") else . end |
  map({
    keyword: .keyword,
    sv: (.keyword_info.search_volume // 0)
  }) |
  map(select(
    .sv >= 150 and
    (.keyword | split(" ") | length) >= 3
  )) |
  sort_by(-.sv) |
  .[0:20]
')

VARIANT_COUNT=$(echo "$VARIANTS" | jq 'length')
if [ "$VARIANT_COUNT" -eq 0 ]; then
  echo '{"data_available": false, "error": "No variants met SV >= 150 threshold"}'
  exit 0
fi

# ── Call 2: keyword_overview ──────────────────────────────────────────────────
KEYWORDS_ARRAY=$(echo "$VARIANTS" | jq '[.[].keyword]')

CALL2_BODY=$(jq -n \
  --argjson kws "$KEYWORDS_ARRAY" \
  '[{"keywords": $kws, "location_code": 2840, "language_code": "en"}]')

CALL2_RESPONSE=$(curl -s -X POST \
  "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_overview/live" \
  -H "Authorization: Basic $AUTH" \
  -H "Content-Type: application/json" \
  -d "$CALL2_BODY")

# ── Merge + Score ─────────────────────────────────────────────────────────────
echo "$CALL2_RESPONSE" | jq \
  --arg seed "$SEED_KW" \
  --argjson variants "$VARIANTS" '
  .tasks[0] |
  if .status_code != 20000 then
    error("Call 2 failed: \(.status_message)")
  else . end |
  .result[0].items |
  if (. == null or length == 0) then error("Call 2 returned no items") else . end |

  # Build KD + intent map
  (reduce .[] as $item (
    {};
    .[$item.keyword] = {
      kd: ($item.keyword_properties.keyword_difficulty // null),
      intent: ($item.search_intent_info.main_intent // null)
    }
  )) as $kd_map |

  # Merge SV (Call 1) + KD/intent (Call 2)
  ($variants | map({
    keyword: .keyword,
    sv: .sv,
    kd: ($kd_map[.keyword].kd // null),
    intent: ($kd_map[.keyword].intent // null)
  })) as $merged |

  # Score: KD <= 70 wins; fallback to lowest KD if none qualify
  ($merged | map(select(.kd != null and .kd <= 70))) as $qualified |
  (if ($qualified | length) > 0
    then {
      winner: ($qualified | max_by(.sv)),
      fallback_applied: false
    }
    else {
      winner: ($merged | map(select(.kd != null)) | min_by(.kd) // null),
      fallback_applied: true
    }
  end) as $scored |

  {
    data_available: true,
    seed_kw: $seed,
    winner: $scored.winner,
    all_variants: $merged,
    fallback_applied: $scored.fallback_applied
  }
'

#!/usr/bin/env bash
# _api.sh: shared API helpers for the refresh scripts (source it, don't run it).
#
# Each service works in either of two modes, chosen from .env:
#   webhook (Raisa's n8n):  DATAFORSEO_WEBHOOK_URL / GEMINI_WEBHOOK_URL
#   direct (own keys):      DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD / GEMINI_API_KEY
# The webhook wins when both are set. The webhooks are thin proxies, so both modes
# send the same request and return the same JSON.
#
# dfs_post  '{"endpoint": "https://api.dataforseo.com/v3/...", "body": [...]}'
# gemini_post '<generateContent request body>'
# Both print the raw JSON response; they exit non-zero on a transport failure.

GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"

require_dfs() {
  if [ -z "${DATAFORSEO_WEBHOOK_URL:-}" ] && { [ -z "${DATAFORSEO_LOGIN:-}" ] || [ -z "${DATAFORSEO_PASSWORD:-}" ]; }; then
    echo "DataForSEO is not configured: set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD (or DATAFORSEO_WEBHOOK_URL) in .env" >&2
    exit 1
  fi
}

require_gemini() {
  if [ -z "${GEMINI_WEBHOOK_URL:-}" ] && [ -z "${GEMINI_API_KEY:-}" ]; then
    echo "Gemini is not configured: set GEMINI_API_KEY (or GEMINI_WEBHOOK_URL) in .env" >&2
    exit 1
  fi
}

dfs_post() {
  if [ -n "${DATAFORSEO_WEBHOOK_URL:-}" ]; then
    curl -s --max-time 120 -X POST "$DATAFORSEO_WEBHOOK_URL" -H "Content-Type: application/json" -d "$1"
  else
    local endpoint body
    endpoint=$(printf '%s' "$1" | jq -r '.endpoint')
    body=$(printf '%s' "$1" | jq -c '.body')
    curl -s --max-time 120 -X POST "$endpoint" -u "${DATAFORSEO_LOGIN}:${DATAFORSEO_PASSWORD}" \
      -H "Content-Type: application/json" -d "$body"
  fi
}

gemini_post() {
  if [ -n "${GEMINI_WEBHOOK_URL:-}" ]; then
    curl -s --max-time 120 -X POST "$GEMINI_WEBHOOK_URL" -H "Content-Type: application/json" -d "$1"
  else
    curl -s --max-time 120 -X POST \
      "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent" \
      -H "x-goog-api-key: ${GEMINI_API_KEY}" -H "Content-Type: application/json" -d "$1"
  fi
}

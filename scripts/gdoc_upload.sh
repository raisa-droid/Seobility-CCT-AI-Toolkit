#!/usr/bin/env bash
# gdoc_upload.sh
# Creates a Google Doc from an HTML file through an n8n webhook, so Claude never
# has to read the HTML and retype it into the Drive connector's create_file call
# (that round trip is about a quarter of a /refresh-fix run). The workflow behind
# the webhook is specified in docs/n8n-gdoc-upload.md.
#
# Usage: ./scripts/gdoc_upload.sh "Doc title" file.html [folder_id]
#   folder_id defaults to REFRESH_FOLDER_ID from .env; if both are empty the Doc lands in My Drive.
#
# Needs in .env (see env.example):
#   GDRIVE_WEBHOOK_URL     the production URL of the n8n workflow
#   GDRIVE_WEBHOOK_TOKEN   optional; sent as the X-Refresh-Token header (the n8n
#                          webhook's Header Auth credential)
#
# Request:  POST JSON {"title": "...", "folder_id": "...", "html": "<full HTML>"}
# Response: JSON {"ok": true, "id": "<doc id>", "url": "https://docs.google.com/document/d/<id>/edit"}
#           or {"ok": false, "error": "..."}
#
# Exit codes: 0 Doc created (the first line of output has its URL),
#             4 not configured (GDRIVE_WEBHOOK_URL is empty): use the Drive connector instead,
#             5 the upload failed (the reason is printed): use the Drive connector instead,
#             1 bad arguments.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

# A value already in the environment wins over .env (handy for testing).
_URL="${GDRIVE_WEBHOOK_URL:-}"; _TOKEN="${GDRIVE_WEBHOOK_TOKEN:-}"
if [ -f "$REPO/.env" ]; then
  source "$REPO/.env"
fi
GDRIVE_WEBHOOK_URL="${_URL:-${GDRIVE_WEBHOOK_URL:-}}"
GDRIVE_WEBHOOK_TOKEN="${_TOKEN:-${GDRIVE_WEBHOOK_TOKEN:-}}"

if [ $# -lt 2 ] || [ ! -f "$2" ]; then
  echo "Usage: gdoc_upload.sh \"Doc title\" file.html [folder_id]" >&2
  exit 1
fi
TITLE="$1"; FILE="$2"; FOLDER="${3:-${REFRESH_FOLDER_ID:-}}"   # empty = My Drive root

if [ -z "$GDRIVE_WEBHOOK_URL" ]; then
  echo "NOT CONFIGURED: GDRIVE_WEBHOOK_URL is empty. Create the Doc with the Drive connector's create_file instead." >&2
  exit 4
fi

PAYLOAD="$(mktemp)"; RESPONSE="$(mktemp)"
trap 'rm -f "$PAYLOAD" "$RESPONSE"' EXIT
jq -n --arg title "$TITLE" --arg folder "$FOLDER" --rawfile html "$FILE" \
  '{title: $title, folder_id: $folder, html: $html}' > "$PAYLOAD"

HEADERS=(-H "Content-Type: application/json")
[ -n "$GDRIVE_WEBHOOK_TOKEN" ] && HEADERS+=(-H "X-Refresh-Token: $GDRIVE_WEBHOOK_TOKEN")

CODE=$(curl -s -S --max-time 120 -o "$RESPONSE" -w '%{http_code}' -X POST "$GDRIVE_WEBHOOK_URL" \
  "${HEADERS[@]}" --data-binary @"$PAYLOAD" 2>&1)
CURL_STATUS=$?
if [ $CURL_STATUS -ne 0 ]; then
  echo "UPLOAD FAILED: could not reach the webhook ($CODE). Create the Doc with the Drive connector's create_file instead." >&2
  exit 5
fi

if ! jq -e . "$RESPONSE" >/dev/null 2>&1; then
  echo "UPLOAD FAILED: HTTP $CODE and the response was not JSON: $(head -c 200 "$RESPONSE"). Create the Doc with the Drive connector's create_file instead." >&2
  exit 5
fi

OK=$(jq -r '.ok // false' "$RESPONSE")
URL=$(jq -r '.url // empty' "$RESPONSE")
if [[ "$CODE" != 2* ]] || [ "$OK" != "true" ] || [ -z "$URL" ]; then
  echo "UPLOAD FAILED: HTTP $CODE: $(jq -r '.error // .message // tostring' "$RESPONSE" | head -c 300). Create the Doc with the Drive connector's create_file instead." >&2
  exit 5
fi

echo "Created Google Doc: $URL"
echo "Doc id: $(jq -r '.id // empty' "$RESPONSE")"

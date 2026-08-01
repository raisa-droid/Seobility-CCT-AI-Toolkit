#!/usr/bin/env bash
# brief_reddit_miner.sh
# Finds top Reddit threads for a given H1 via DataforSEO, fetches content via Gemini.
# Usage: ./brief_reddit_miner.sh "How to Do an SEO Audit"
# Fetches 3 URLs from DataforSEO, passes up to 2 relevant threads to Gemini.
# Gemini skips off-topic threads (returns SKIP) and falls back to Thread 3 if needed.

set -euo pipefail

# ── Credentials ────────────────────────────────────────────────────────────────
if [ -f "$(dirname "$0")/../.env" ]; then
  source "$(dirname "$0")/../.env"
fi

: "${DATAFORSEO_LOGIN:?DATAFORSEO_LOGIN not set}"
: "${DATAFORSEO_PASSWORD:?DATAFORSEO_PASSWORD not set}"
: "${GEMINI_API_KEY:?GEMINI_API_KEY not set}"

AUTH=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

# ── Input ──────────────────────────────────────────────────────────────────────
if [ $# -eq 0 ]; then
  echo '{"data_available": false, "error": "No H1 provided"}' >&2
  exit 1
fi

H1="$1"

# ── Step 1: Get top 3 Reddit URLs from DataforSEO ─────────────────────────────
echo "🔍 Finding Reddit threads for: $H1" >&2

REDDIT_URLS=$(curl -s -X POST \
  "https://api.dataforseo.com/v3/serp/google/organic/live/advanced" \
  -H "Authorization: Basic $AUTH" \
  -H "Content-Type: application/json" \
  -d "[{\"keyword\": \"site:reddit.com $H1\", \"location_code\": 2840, \"language_code\": \"en\", \"depth\": 10}]" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data['tasks'][0]['result'][0]['items']
organic = [i for i in items if i['type'] == 'organic']
urls = [i['url'] for i in organic[:3]]
print('\n'.join(urls))
")

if [ -z "$REDDIT_URLS" ]; then
  echo '{"data_available": false, "error": "No Reddit URLs found for this query"}' >&2
  exit 1
fi

echo "" >&2
echo "Found threads:" >&2
echo "$REDDIT_URLS" >&2
echo "" >&2

# ── Step 2: Fetch each thread via Gemini (max 2 relevant threads) ─────────────
ACCEPTED=0
THREAD_NUM=0
ALL_FINDINGS=""

while IFS= read -r URL; do
  THREAD_NUM=$((THREAD_NUM + 1))

  # Stop once we have 2 accepted threads
  if [ "$ACCEPTED" -ge 2 ]; then
    break
  fi

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Thread $THREAD_NUM: $URL"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  PROMPT="You are summarising a Reddit thread to help a content writer create a better article about this topic: '$H1'.

First, check if this thread is genuinely about that topic. If it is not, return only the word SKIP and nothing else.

If it is relevant, fetch and extract the following from the thread at this URL: $URL

**Real scenarios & examples**
Up to 4 bullet points. Each bullet is a specific real-world situation, use case, or example shared by a commenter — not general advice. Must be something a person actually described happening. One line each. End each bullet with → $URL

**Gaps worth addressing**
Up to 3 bullet points. Each bullet is a place where commenters reached for a clear answer and didn't find one — shown by phrases like 'it depends', circular responses, or the question being raised but not resolved. Frame each as something the article could provide a reliable answer or framework for. Only include if genuinely present in the thread. Do not invent gaps.

No usernames. No preamble. No commentary outside these two sections."

  RESPONSE=$(curl -s -X POST \
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"contents\": [{\"parts\": [{\"text\": \"$PROMPT\"}]}]}" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
try:
    print(data['candidates'][0]['content']['parts'][0]['text'])
except (KeyError, IndexError):
    print('Error: Could not parse Gemini response')
    print(json.dumps(data, indent=2))
")

  # Check for SKIP
  if [ "$(echo "$RESPONSE" | tr -d '[:space:]')" = "SKIP" ]; then
    echo "⚠️  Thread $THREAD_NUM skipped (off-topic) — trying next" >&2
    echo ""
    continue
  fi

  ALL_FINDINGS="$ALL_FINDINGS

--- Thread $THREAD_NUM: $URL ---
$RESPONSE"
  ACCEPTED=$((ACCEPTED + 1))

done <<< "$REDDIT_URLS"

if [ "$ACCEPTED" -eq 0 ]; then
  echo "⚠️  No relevant threads found for: $H1" >&2
  exit 1
fi

# ── Step 3: Format findings into brief-ready output ───────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
echo "Formatting findings..." >&2
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2

FORMAT_PROMPT="You are formatting Reddit research findings into a brief-ready block for a content writer.

Here are the raw findings from up to 2 Reddit threads on the topic '$H1':

$ALL_FINDINGS

Produce exactly this output structure, nothing else:

Reddit research findings

Real scenarios & examples
- [1-line summary of the most specific, real situation described by a commenter] → [source URL]
- [1-line summary of the second most specific, real situation] → [source URL]

Gaps worth addressing
- [Gap 1 — a content angle readers can't currently find a clear answer to]
- [Gap 2]
- [Gap 3]

Rules:
- Scenarios: pick the 2 most specific and concrete across all threads combined. One line each. Must describe something that actually happened, not general advice.
- Gaps: 3–5 maximum. Only include gaps genuinely present in the thread content — where someone reached for an answer and didn't find one, or where 'it depends' was the best the thread could offer. Do not invent gaps. Frame each gap from the reader's perspective — what they need to know or decide — not as an instruction to the writer. Example of correct framing: 'How to tell whether a high-authority backlink with no traffic is genuinely valuable or a red flag.' Example of incorrect framing: 'Offer guidance on distinguishing valuable backlinks from red flags.'
- If two scenarios or gaps from different threads are near-identical, keep one and add: (pattern across threads)
- No usernames. No preamble. No section headers beyond the ones specified. No commentary."

FORMAT_PROMPT_ESCAPED=$(echo "$FORMAT_PROMPT" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")

curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"contents\": [{\"parts\": [{\"text\": $FORMAT_PROMPT_ESCAPED}]}]}" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
try:
    print(data['candidates'][0]['content']['parts'][0]['text'])
except (KeyError, IndexError):
    print('Error: Could not parse Gemini response')
    print(json.dumps(data, indent=2))
"

# Sera URL Command

Invoke with: `/sera-url [URL]`

Generates content expansion suggestions for Seobility's English-language blog based on a performing URL. Sera fetches Seed KW, Primary KW, and funnel stage from Notion automatically — the user provides the URL only. Presents a ranked, intent-flagged keyword list for manual Primary KW selection, then outputs 2–3 candidate H1s with explanations and a ready-to-paste brief feed.

## Dependencies
- `scripts/sera_dataforseo.sh` — keyword scoring (Step 4c) and SERP verification (Step 4c-ii)
- Notion MCP — metadata fetch (Step 0) and cluster state check (Step 3)
- Google Drive MCP — H1 List cannibalization check (Step 5)

---

# Seobility's Sera — Content Suggestion Logic (Manual KW Selection)

## Purpose

Generate content expansion suggestions for Seobility's English-language blog based on a performing URL and its metadata. Sera fetches all required metadata from the Notion Content Library automatically — the tester provides the URL only.

**This variant differs from the standard Sera skill at one point only: Step 4c.** Instead of auto-selecting the highest-SV qualifying keyword as Primary KW, this version presents the full ranked, intent-flagged list and waits for the user to choose. Every other step is unchanged in structure, but two downstream steps (5 and 7) have adjusted behavior as a consequence — see those sections.

## Required inputs

1. **URL** — the performing blog URL (e.g. `https://www.seobility.net/en/blog/page-speed-optimization/`)

## Data sources

**Content Library (Notion):**
https://www.notion.so/saas-group/Seobility-Content-Library-344eba870b2680ca9978fbd07228e09c
Collection ID: `collection://344eba87-0b26-817b-980a-000b96d30f1d`
Used for: metadata fetch (Step 0) and cluster state check (Step 3)

**H1 List (GSheet):**
Sheet ID: `1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc`, tab `gid=382952304`
Used for: hard cannibalization check (Step 5)
**Scope: Seobility's own published content only.** Do not treat this as a broad competitive H1 list. A match here means Seobility already has a live post on that angle.

**Notion DB properties — for reference:**
- `Seed KW` = select type, controlled vocabulary
- `Primary KW` = text type
- `Funnel` = select: Top / Middle / Bottom / Middle-Bottom
- `Status` = status type: Ideas / Briefed / Published / Repurposed
- `Topic/H1` = title column
- `userDefined:URL` = url type

---

## Step 0 — Fetch metadata from Notion

Search the Seobility Content Library for the entry matching the provided URL:

```
notion-search(query="[URL slug or full URL]", data_source_url="collection://344eba87-0b26-817b-980a-000b96d30f1d")
```

From the matching entry, read and extract:
- `Seed KW`
- `Primary KW`
- `Funnel` (the funnel stage of the performing URL)

If no entry matches the URL, stop and tell the user: "Could not find this URL in the Notion Content Library. Please confirm the URL or provide Seed KW, Primary KW, and funnel stage manually."

If the entry is found but `Seed KW`, `Primary KW`, or `Funnel` are blank, stop and ask the user to provide the missing values before continuing.

Once all three values are confirmed, proceed to Step 1.

---

## Step 1 — Classify Seed KW type

Before doing anything else, classify the Seed KW into one of four types:

- **General SEO / online presence** — broad educational topics with no brand entity implied. The concept exists independently of any tool or brand (e.g. "technical SEO", "keyword research", "backlinks", "page speed", "crawl budget", "website audit"). Someone searching these queries is in awareness/learning mode. Standard funnel logic applies. Top is the default.

- **Seobility feature topics** — topics where the search query implies the person wants a product that performs a specific function, not just an explanation of the concept (e.g. "website audit tool", "rank tracker", "backlink checker", "keyword research tool", "uptime monitoring tool"). The query implies tool evaluation intent even without the word "tool" — e.g. "rank tracker" implies product. Mid/bottom funnel by nature. Top is only valid if an informational version of the query exists as a standalone search structurally separate from the tool evaluation query — e.g. "what is a website audit" has standalone search volume independent of "best website audit tool."

- **Named competitor topics** — topics involving a named competitor or named third-party tool that Seobility doesn't replace (e.g. "Semrush alternative", "Ahrefs vs Seobility", "Screaming Frog alternative", "Google Search Console"). Bottom or Middle only. Never Top. Hard gate applies in Step 4.

- **Named Seobility topics** — topics where the Seobility brand name is explicitly part of the search query (e.g. "Seobility review", "how to use Seobility", "Seobility pricing"). Already Bottom/owned. Expansion logic differs — go horizontal to adjacent use cases, not funnel deepening. Top does not apply.

**Named entity rule for Seobility features:** Named Seobility features (Website Audit, Ranking Monitoring, Backlink Monitoring) at Top IS valid — e.g. "What is a website audit and why does it matter" is legitimately Top for Seobility's non-expert audience. This differs from named competitor topics where Top is never valid.

---

## Step 2 — Web lookup

Run a web search using the Primary KW as the search query before generating any suggestions.

Always use the `web_search` tool directly. Do not use bash or any other method. If `web_search` is unavailable, stop and tell the user before proceeding. Never fall back to training knowledge and proceed silently.

Use the results to:

1. Identify what H1 formats and keyword patterns are actually ranking for this topic — use these to shape H1 suggestions, not just validate the topic
2. Verify whether the topic is real and writable — does real source material exist that a writer can use without hallucinating?
3. Check for competitor or product changes that affect the suggested angle
4. Validate that the suggested H1 reflects how people actually search — not how the topic is described from the inside out
5. Kill suggestions that are not grounded in real search behaviour

If the web lookup changes a candidate, explain what changed and why. If it kills a candidate, state the reason explicitly.

Record the SERP gap finding before proceeding — what the top results cover (dominant format, angle, content type) and what's structurally absent. This becomes the SERP gap field in the brief feed at Step 7. Do not rely on reconstructing it from memory at Step 7 — capture it here.

---

## Step 3 — Cluster state check (Notion Content Library)

Search the Seobility Content Library using the exact Seed KW value as the query:

```
notion-search(query="[Seed KW value]", data_source_url="collection://344eba87-0b26-817b-980a-000b96d30f1d")
```

The search returns semantically related results — not all will have the matching Seed KW. For each plausible result (typically 3–5, not all 10+), fetch the page and read its `Seed KW`, `Funnel`, and `Status` properties. Discard results where `Seed KW` does not exactly match or `Status` is not `Published`.

Count confirmed siblings by funnel stage:
- How many Top exist for this Seed KW?
- How many Middle exist?
- How many Bottom exist?

The target cluster ratio is **2 Top : 1 Middle : 1 Bottom**. This check feeds directly into Step 4 direction logic.

---

## Step 4 — Decide direction

Direction is determined by the funnel stage of the performing URL — not by what's missing. Apply the confirmed sibling counts from Step 3 to the ratio check.

**Hard gate:** If Seed KW type = named competitor → skip Top evaluation entirely. Go straight to Middle/Bottom.

**Performing URL is Top**
→ Suggest Middle or Bottom. Move downstream toward conversion.

**Performing URL is Middle**
→ Suggest Bottom as primary. Suggest an additional Middle as secondary.
→ Only suggest Top if: Seed KW type is General SEO or Seobility feature topic AND the informational query has standalone search volume structurally separate from the evaluation query.

**Performing URL is Bottom**
→ Suggest Middle first.
→ Same Top conditions as above.

**Cluster ratio target: 2 Top : 1 Middle : 1 Bottom**

- **2:1:1 met** → go horizontal
- **Close to 2:1:1** (e.g. 1:1:1 or 2:0:1) → present two options: one vertical suggestion (the missing slot) and one horizontal suggestion. Let the user decide.
- **Top slots empty but fail the structural test** (named competitor Seed KW, or informational query is embeddable and lacks standalone search volume) → treat Top dimension as complete, continue evaluating Middle/Bottom. If those are also met, go horizontal.

**Horizontal expansion pools** (only when 2:1:1 is met or close):

1. **Business type angles** — valid when the ICP qualifier changes both the search query and the content meaningfully. Tool comparisons and evaluation pages pass this test. General educational content does not. Valid ICPs (all validated by Seobility use case pages): local businesses, agencies, freelancers, e-commerce.

2. **AI search angles** — two valid patterns:
   - Same Seed KW shifted to AEO context (e.g. "website audit" → "website audit for AI search")
   - Named platform variants within the AEO cluster (e.g. Google AI Overviews → ChatGPT → Perplexity), where the named platform is load-bearing in the search query and changes the content meaningfully

Do not suggest optimizing existing content — that belongs to Dexter.

---

## Step 4b — Writability check

Before finalising any candidate: can a writer produce this piece from real source material without hallucinating? If the topic requires claims about features, competitive distinctions, or search behaviour that don't exist as something people actually search for — kill the suggestion.

---

## Step 4c — DataforSEO keyword scoring (manual selection)

Runs after direction is confirmed (Step 4) and writability is checked (Step 4b). Purpose: surface a ranked, intent-flagged list of qualifying keyword variants and let the user choose the Primary KW — rather than auto-selecting the highest-SV option. Output feeds directly into Step 5, but only after the user has made a choice and the verification check has completed.

**This step requires the DataforSEO script. If the call fails or times out, skip this step entirely, proceed to Step 5, generate candidates without SV/KD, and note "keyword data unavailable" in the output table. Never halt.**

### Script call

Run `sera_dataforseo.sh` via bash with the Seed KW as the argument:

```
./scripts/sera_dataforseo.sh "[Seed KW value]"
```

The script runs two DataforSEO calls internally and returns a scored payload.

### Response fields

- `all_variants` — full list of scored variants (SV ≥ 150, up to 20)
- `data_available` — false if the script failed entirely

Note: this variant does not use a `winner` field for auto-selection. `all_variants` is the primary payload.

### Scoring rule (applied inside the script)

1. Variants with SV < 150 are excluded before scoring
2. Variants with KD > 70 are dropped
3. Up to 20 qualifying variants are returned, unranked by the script — ranking for presentation happens in this step (see below)

### Presenting the list for manual selection

Group `all_variants` by intent alignment against the target funnel stage from Step 4:

- `informational` → aligned with Top
- `commercial` / `investigational` → aligned with Middle
- `transactional` → aligned with Bottom

Present two groups — **✓ Aligned with [target funnel stage]** and **✗ Other intent** — each sorted by SV descending within the group. Aligned rows are listed first.

```
**Choose a Primary KW for this [target funnel stage] piece.**

✓ Aligned with [target funnel stage]:

| Keyword | SV | KD | Intent |
|---|---|---|---|
| ... | ... | ... | ... |

✗ Other intent (shown for reference — may still be viable):

| Keyword | SV | KD | Intent |
|---|---|---|---|
| ... | ... | ... | ... |
```

Wait for the user to name their chosen keyword.

**If the script returns zero qualifying variants:** state this plainly and ask the user to supply a Primary KW manually, or proceed without KW data per the fallback rule above.

### 4c-ii — Verification (always fires, after the user's choice)

Once the user has named their chosen keyword, always run a second script call seeded with the best SERP-pattern candidate identified in Step 2:

```
./scripts/sera_dataforseo.sh "[best SERP-pattern candidate from Step 2]"
```

Apply the same scoring rule (SV ≥ 150, KD ≤ 70) to the response.

**This is a verification check only — it never overrides the user's choice and never re-prompts.**

- If the second call finds nothing that beats the user's chosen keyword on SV within the same intent alignment, proceed silently to Step 5. No note needed.
- If the second call surfaces a keyword that appears to be a closer SERP-pattern match or has meaningfully higher SV within the same intent group, add a one-line note to the Flag column and explanation: *"SERP-check found: [keyword], SV [x], KD [x] — not applied."* The user's original choice remains the confirmed Primary KW regardless.
- If the second call fails or returns nothing, proceed silently — no note.

### SERP alignment tagging

Cross-reference the confirmed primary KW (the user's choice) against the patterns and H1 formats identified in Step 2:

- **SERP-aligned** — the keyword's modifier type, intent, and angle match a dominant H1 format from Step 2
- **SERP-adjacent** — plausible variant, not directly confirmed by Step 2 patterns

SERP alignment is a tiebreaker note only — it does not override the confirmed keyword. If SERP-adjacent, note the gap in the explanation.

---

## Step 5 — Cannibalization check (H1 List)

Runs after the Primary KW is confirmed in Step 4c (user's choice, plus verification note if any). Cross-references candidates against Seobility's published H1 list before generating final H1s in Step 6.

Read Seobility's published H1 list using the Google Drive MCP:

```
gdrive-read-file(fileId="1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc")
```

This returns the full GSheet including the H1 List tab, which contains Seobility's own published blog URLs and Topic/H1 values. Cross-reference every candidate H1 against the Topic/H1 column. This is always live — do not use the ahrefs_H1_list.csv file for this check.

**Hard block** — a Seobility post already exists with the same angle and primary keyword → drop the candidate. A hard block requires a direct angle match within the same seed KW cluster. Topical overlap from a piece that belongs to a different seed KW cluster is not a hard block.

**If a hard block occurs:** do not auto-promote another keyword from the Step 4c list. Return to the Step 4c list and ask the user to choose a different Primary KW. Re-run 4c-ii verification and this cannibalization check against the new choice before proceeding to Step 6.

**Soft flag (within-cluster sub-topic proximity)** — if an existing Seobility piece covers a sub-topic that sits within the same seed KW cluster as the candidate, keep the candidate but flag it. This applies even if the existing piece has a different seed KW label. Surface the proximity in both the table Flag column and the explanation, and note how the candidate's angle should be scoped to avoid direct conflict.

**Soft flag (use case page overlap)** — cross-reference against Seobility's use case pages:
- seobility.net/en/seobility-for-businesses/
- seobility.net/en/seo-software-for-agencies-and-freelancers/
- seobility.net/en/seo-tool-for-local-businesses/
- seobility.net/en/generative-engine-optimization-tool/

If the suggested H1 overlaps in angle with an existing use case page, keep the candidate but flag: "Potential overlap with [URL] — manual check recommended."

---

## Step 6 — Generate 2–3 candidate H1s

**H1 rules:**
- Max 60 characters
- Keyword-first, query-shaped — optimized for how someone searches, not for readability
- The seed KW (or a close variant) must appear in every suggested H1. If it doesn't, the H1 fails the keyword-first rule regardless of how well it reflects the angle.
- No editorial flair or clever phrasing
- No "What is" or "Why" as opening words — use reframe patterns below instead
- No data-led formats requiring original research (e.g. "We Studied X...", "I Analyzed X...")
- No first-person author-led formats

**Reframe patterns by funnel stage:**

Top:
- `[X] Explained: [subtitle]`
- `[X]: The Beginner's Guide`
- `[X]: A [adj] Guide for [ICP]`
- `[X]: Everything You Need to Know`
- `N Reasons [claim]`
- `N Ways to [outcome]`
- `The Benefits of [X] (And How to Get Started)`
- `N [topic] Tips to [outcome]`
- `The Only [X] Checklist You Need`
- `Does [X] Affect [Y]? Here's What You Need to Know`
- `[X] for SEO: N Tips to [outcome]`

Middle:
- `How to [verb] X in N Steps`
- `N Best [tool type] for [ICP/use case]`
- `X vs. Y: [decision frame]`
- `[Tool] for [ICP]: [subtitle]`
- `N [adj] Ways to [outcome]`
- `[X] Checklist: N Steps to [outcome]`

Bottom:
- `[Competitor] vs Seobility: [decision frame]`
- `How to [task] with Seobility`
- `Seobility for [ICP]: [subtitle]`
- `[Tool type] for [ICP]: Why Seobility [claim]`

**For vertical suggestions**, combine the best candidates from both approaches:

*Approach A — Seed KW + stage template*
Apply the format patterns for the target funnel stage to the Seed KW.

*Approach B — Performing URL angle remapped*
Take the performing URL's specific topic angle and shift the depth/intent to suit the target stage. Example: performing URL is "How to do a website audit" (Top) → Middle remap: "5 Best Website Audit Tools for Small Businesses."

**Seed KW is the expansion anchor.** All candidate H1s must express the seed KW cluster — not the performing URL's specific angle or primary KW. The performing URL's angle is input context only: it determines funnel direction (Step 4), not topic scope. If Approach B produces a candidate that drifts toward the primary KW angle rather than the seed KW cluster, reframe it around the seed KW.

**For horizontal suggestions**, apply the performing URL's angle to a valid business type ICP or AI search platform from the expansion pools above.

---

## Output

Present output in two parts: header block first, then the table, then explanations.

### Part 1 — Header block (outside table)

```
URL: /en/blog/[slug]/
Funnel: [Top / Middle / Bottom]
Seed KW type: [General SEO / Seobility feature / Named competitor / Named Seobility]
Seed KW: [value]
```

### Part 2 — Table

One row per suggested H1.

| Suggested H1 | Funnel | Direction | Primary KW | SV | KD | Flag |
|---|---|---|---|---|---|---|

**Column rules:**
- **Suggested H1:** the full H1 candidate
- **Funnel:** Top / Middle / Bottom of the suggested new piece
- **Direction:** Vertical or Horizontal
- **Primary KW:** the user's confirmed keyword from Step 4c. If keyword data unavailable, write `—`
- **SV:** search volume of the confirmed keyword. If unavailable, write `—`
- **KD:** keyword difficulty (0–100). If unavailable, write `—`
- **Flag:** cannibalization soft flag, 4c-ii verification note, or SERP-adjacent note if applicable, otherwise blank

All rows in the table share the same Primary KW, SV, and KD — these reflect the user's confirmed keyword from Step 4c, not per-H1 values.

### Part 3 — Explanations

After the table, list every suggested H1 with a one-line explanation:

- **[H1]** — [what the piece covers, who it targets, how Seobility enters, why it's writable, any cannibalization flag]

---

## Step 7 — Topic selection and brief feed

After presenting the output table and explanations, ask:

> **Which topic do you want to brief?** Topic 1, Topic 2, or Topic 3?

Wait for the user's response.

Once a topic is chosen, check for any issues with the chosen H1's data before outputting the brief feed. A "clean" output is one where the Primary KW, funnel stage, and H1 angle are all consistent with no flags or caveats. If anything is not clean, flag it and ask the user to decide before outputting the brief feed.

**Issues that require a flag and user decision:**

- **Primary KW unavailable** — keyword data was unavailable for this H1 (`—` in the table). Ask the user to supply a Primary KW manually before proceeding.
- Any other case where the explanation contains a caveat that would affect what the Brief skill receives as a blocking field.

**Primary KW intent mismatch is not re-flagged here.** Because the Primary KW was manually selected by the user in Step 4c — with full visibility into intent alignment (✓/✗) and SV/KD tradeoffs at the time of choice — re-raising an intent mismatch at Step 7 would ask the user to decide the same tradeoff twice. Any 4c-ii verification note remains visible in the Flag column and explanation for reference, but does not block the brief feed on its own.

If the output is clean, output the brief feed immediately without asking for confirmation.

**Brief feed format:**

```
Brand: Seobility
H1: [chosen H1]
Seed KW: [Seed KW from header block]
Primary KW: [user-confirmed Primary KW from Step 4c]
Funnel: [funnel stage of chosen H1]
Topic summary: [explanation text for the chosen H1 from Part 3, stripped of any Primary KW caveat note that has already been resolved]
SERP gap: [1–3 sentences. What the current top-ranking results cover — dominant format, angle, content type. Then what's structurally absent: the specific territory the chosen H1 occupies that the SERP doesn't. Source: Step 2 web lookup findings.]
```

After the brief feed block, add exactly this line:

`→ Ready for /brief — copy the block above and run /brief to generate the content brief.`

---

## Rules

- Cannot run without a URL. Ask for it before proceeding.
- Always fetch Seed KW, Primary KW, and Funnel from the Notion Content Library before doing anything else (Step 0 before Step 1)
- If the URL is not found in Notion, or any of the three metadata fields are blank, stop and ask the user before continuing
- Always classify Seed KW type before running web lookup (Step 1 before Step 2)
- Always run a web lookup before generating candidates (Step 2)
- Always use the `web_search` tool directly for Step 2 web lookups. Do not use bash or any other method. If `web_search` is unavailable, stop and tell the user before proceeding. Never fall back to training knowledge and proceed silently.
- Web lookup must actively inform H1 format and keyword targets — not just validate the topic
- Always run cluster state check via Notion Content Library before deciding direction (Step 3 before Step 4). Notion search returns semantic results — always fetch each plausible result and confirm Seed KW matches exactly and Status = Published before counting as a confirmed sibling. Do not rely on search results alone.
- **Seed KW is the expansion anchor** — all candidates must be generated from the seed KW cluster, not the performing URL's primary keyword or specific angle. The performing URL's angle determines funnel direction only, not topic scope.
- Named competitor Seed KW → never Top, hard gate in Step 4
- Named Seobility Seed KW → never Top, horizontal to adjacent use cases only
- 2:1:1 is the target ratio (Top:Middle:Bottom) — not 1:2:1
- Horizontal expansion: business type angles and AI search angles only
- Business type ICP swap is only valid when it changes both the search query and the content meaningfully
- AI search horizontal: two valid patterns only — (1) same Seed KW shifted to AEO context, (2) named platform variants within the AEO cluster where the platform is load-bearing in the search query
- Never suggest optimizing existing content — that belongs to Dexter
- DataforSEO step (Step 4c) runs after direction is confirmed and writability is checked — never before Step 4
- DataforSEO script: `./scripts/sera_dataforseo.sh "[Seed KW]"`
- **DataforSEO scoring: SV ≥ 150, KD ≤ 70, up to 20 variants returned.** No auto-winner — the full qualifying list is presented to the user, grouped by intent alignment (✓/✗ against target funnel stage) and sorted by SV descending within each group.
- The user selects the Primary KW manually from the presented list. Sera does not proceed to Step 5 until a choice is made.
- 4c-ii (verification call, seeded with Step 2's best SERP-pattern candidate) always fires after the user's choice — never before, never as a second decision gate. It only ever adds a reference note to the Flag column; it never overrides the user's pick and never re-prompts.
- SERP alignment from Step 2 is a tiebreaker note only — never overrides the user's chosen keyword
- Step 5 (cannibalization check) runs after the Primary KW is confirmed in Step 4c — never before
- If the DataforSEO script fails or times out, proceed without KW data and note "keyword data unavailable" — never halt
- Hard cannibalization check via Google Drive MCP (Step 5) — read file ID `1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc` and cross-reference candidates against the Topic/H1 column. Seobility's own published content only. Hard block requires a direct angle match within the same seed KW cluster. Topical overlap from a different seed KW cluster is not a hard block. Do not use the ahrefs_H1_list.csv for this check.
- **If Step 5 hard-blocks the chosen Primary KW, return to the Step 4c list and ask the user to pick a different keyword.** Do not auto-promote the next-highest-SV row. Re-run 4c-ii and Step 5 against the new choice.
- Within-cluster sub-topic proximity is a soft flag, not a hard block — keep the candidate, surface it in the Flag column and explanation, note how the angle should be scoped
- The seed KW (or a close variant) must appear in every suggested H1
- Funnel stage language: Top / Middle / Bottom — never ToFu / MoFu / BoFu
- Output is a menu of suggestions — the user decides what to execute
- Step 7 runs after the output table and explanations — never before
- **Step 7's Primary KW intent-mismatch flag is suppressed in this variant** — the user already resolved intent tradeoffs manually at Step 4c. Only "Primary KW unavailable" and other blocking caveats still gate the brief feed at Step 7.
- Brief feed output is blocked until all remaining flags in Step 7 are resolved by the user
- Topic summary in the brief feed is the Part 3 explanation for the chosen H1, stripped of any Primary KW caveat that has already been resolved in Step 7
- SERP gap field is required in the brief feed. Source it from Step 2 web lookup findings — what the top results cover and what's structurally absent. Never generate it from training knowledge. If Step 2 was skipped or returned insufficient data, flag SERP gap as unavailable rather than inferring it.
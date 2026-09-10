# Sera Keyword Command

Invoke with: `/sera-kw` or `/sera-keyword` followed by labeled fields:

```
/sera-kw primary kw: [primary kw] seed kw: [seed kw]
/sera-keyword primary kw: [primary kw] seed kw: [seed kw]
```

Both trigger forms are valid. Label format is flexible — parsed regardless of punctuation or line breaks.

Generates content expansion suggestions for Seobility's English-language blog starting from a known Primary KW. Use when you have identified a keyword gap through external research and already know the Primary KW you want to target.

## Dependencies
- `scripts/brief_dataforseo.sh` — single-phrase SERP verification call (Step 4c-ii)
- Notion MCP — Content Library cluster state check (Step 3)
- Google Drive MCP — H1 List cannibalization check (Step 5)
- `product-context/seobility_features.md` — product capability check for Middle/Bottom suggestions (Step 4c)

---

# Seobility's Sera — Content Suggestion Logic (Keyword Entry)

## Purpose

Generate content expansion suggestions for Seobility's English-language blog starting from a known Primary KW — not a performing URL. Use this variant when you have identified a keyword gap through external research and already know the Primary KW you want to target.

**This variant differs from seobility-sera-manual-select in three ways:**
1. No URL input. No Notion metadata fetch (Step 0 is skipped entirely).
2. Primary KW and Seed KW are provided directly by the user.
3. Step 4 direction logic is cluster-state-based, not performing-URL-based — Sera recommends a funnel stage from the 2:1:1 ratio check and validates it against Primary KW intent.
4. Step 4c (DataforSEO scoring and manual KW selection) is skipped — the Primary KW is already confirmed. Step 4c-ii (SERP verification) still fires.

All other steps are identical to seobility-sera-manual-select.

## Trigger

Fires on `run sera kw` or `run sera keyword`, followed by labeled fields:

```
run sera kw. primary kw: [primary kw], seed kw: [seed kw]
```

Label format is flexible — Sera parses `primary kw:` and `seed kw:` from whatever follows the trigger, regardless of punctuation or line breaks between them.

## Required inputs

1. **Primary KW** — the keyword you want to target (e.g. `international seo for enterprise`)
2. **Seed KW** — the seed keyword this Primary KW belongs to (e.g. `international seo`)

If either is missing after the trigger fires, ask for the missing value before proceeding. Do not infer or assume either field.

## Data sources

**Content Library (Notion):**
https://www.notion.so/saas-group/Seobility-Content-Library-344eba870b2680ca9978fbd07228e09c
Collection ID: `collection://344eba87-0b26-817b-980a-000b96d30f1d`
Used for: cluster state check (Step 3)

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

## Step 1 — Classify Seed KW type

Before doing anything else, classify the Seed KW into one of four types:

- **General SEO / online presence** — broad educational topics with no brand entity implied. The concept exists independently of any tool or brand (e.g. "technical SEO", "keyword research", "backlinks", "page speed", "crawl budget", "website audit"). Someone searching these queries is in awareness/learning mode. Standard funnel logic applies. Top is the default.

- **Seobility feature topics** — topics where the search query implies the person wants a product that performs a specific function, not just an explanation of the concept (e.g. "website audit tool", "rank tracker", "backlink checker", "keyword research tool", "uptime monitoring tool"). The query implies tool evaluation intent even without the word "tool" — e.g. "rank tracker" implies product. Mid/bottom funnel by nature. Top is only valid if an informational version of the query exists as a standalone search structurally separate from the tool evaluation query — e.g. "what is a website audit" has standalone search volume independent of "best website audit tool."

- **Named competitor topics** — topics involving a named competitor or named third-party tool that Seobility doesn't replace (e.g. "Semrush alternative", "Ahrefs vs Seobility", "Screaming Frog alternative", "Google Search Console"). Bottom or Middle only. Never Top. Hard gate applies in Step 4.

  **AI search platform exception:** Named AI search platforms referenced as themselves for AEO purposes (e.g. Google AI Overviews, ChatGPT, Perplexity) are not named-competitor topics, even though they're named third-party products — they follow the AEO horizontal-expansion logic in Step 4a instead, and Top is valid for informational angles about the platform itself (e.g. "What Are Google AI Overviews and How Do They Work"). This exception never applies to named SEO-tool competitors Seobility actually competes with (Semrush, Ahrefs, Screaming Frog, etc.) — those remain hard-gated from Top.

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
6. Identify the best SERP-pattern candidate — the keyword or phrasing that most closely matches dominant H1 formats in the results. This candidate seeds the 4c-ii verification call later.

If the web lookup changes a candidate, explain what changed and why. If it kills a candidate, state the reason explicitly.

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

**Alias awareness:** Exact Seed KW matching keeps the ratio count precise, but it can silently drop real siblings that cover the same practical territory under a different (but closely related) Seed KW label — e.g. a feature-specific tracking page filed under an adjacent seed, or a sub-topic piece filed under a different but clearly related seed in the same field. Before finalizing the count, review the results discarded for Seed KW mismatch and check whether any are topical aliases rather than unrelated content. Do not count aliases toward the ratio (the exact-match count stays the basis for ratio math), but do surface them explicitly: "Note: '[Topic/H1]' carries Seed KW '[X]', not '[target Seed KW]', but covers closely related territory — for context only, not counted toward the ratio." This keeps sibling counting real without loosening the Notion vocabulary.

---

## Step 4 — Recommend funnel stage

**This step differs from seobility-sera-manual-select.** There is no performing URL to anchor direction. Instead, Sera derives the recommended funnel stage from two inputs: (1) the cluster state from Step 3, and (2) the Primary KW's intent as observed in the Step 2 SERP results.

### 4a — Gap recommendation from cluster state

Apply the confirmed sibling counts to the 2:1:1 ratio:

**Hard gate:** If Seed KW type = named competitor → skip Top evaluation entirely. Recommend Middle or Bottom only.

- **2:1:1 met** → go horizontal. Recommend a horizontal expansion angle (business type ICP or AI search — see pools below).
- **Top slot missing or underweight** → recommend Top, subject to the structural test: Seed KW type must be General SEO or Seobility feature topic AND the informational query must have standalone search volume structurally separate from the evaluation query. If the structural test fails, treat Top as complete and evaluate the next missing slot.
- **Middle slot missing** → recommend Middle.
- **Bottom slot missing** → recommend Bottom.
- **Close to 2:1:1** (e.g. 1:1:1 or 2:0:1) → present two options: one vertical (the missing slot) and one horizontal suggestion. Let the user decide.

**Horizontal expansion pools** (only when 2:1:1 is met or close):

1. **Business type angles** — valid when the ICP qualifier changes both the search query and the content meaningfully. Tool comparisons and evaluation pages pass this test. General educational content does not. Valid ICPs (all validated by Seobility use case pages): local businesses, agencies, freelancers, e-commerce.

2. **AI search angles** — two valid patterns:
   - Same Seed KW shifted to AEO context (e.g. "website audit" → "website audit for AI search")
   - Named platform variants within the AEO cluster (e.g. Google AI Overviews → ChatGPT → Perplexity), where the named platform is load-bearing in the search query and changes the content meaningfully

Do not suggest optimizing existing content — that belongs to Dexter.

### 4b — Intent check against Primary KW

Cross-reference the gap-recommended funnel stage against the Primary KW's dominant search intent as observed in Step 2 SERP results:

- `informational` intent → aligned with Top
- `commercial` / `investigational` intent → aligned with Middle
- `transactional` intent → aligned with Bottom

**If the recommended funnel stage and the Primary KW intent are aligned:** proceed to Step 4c (writability check). No flag needed.

**If they are misaligned** (e.g. cluster gap says Top but Primary KW intent is clearly commercial): surface the mismatch explicitly and ask the user to decide before proceeding:

> "The cluster gap suggests a **[recommended stage]** piece, but your Primary KW (`[primary kw]`) shows **[observed intent]** intent in the SERP. Do you want to:
> (A) Proceed with **[recommended stage]** — I'll generate H1s anchored to the Seed KW that fit that funnel stage, noting the intent mismatch.
> (B) Switch to **[intent-aligned stage]** — I'll generate H1s that match your Primary KW's intent instead."

Wait for the user's decision before continuing. The chosen funnel stage is the confirmed stage for all downstream steps.

---

## Step 4c — Writability & product capability check

Two independent checks must both pass before finalising any candidate:

**Writability** — can a writer produce this piece from real source material without hallucinating? If the topic requires claims about features, competitive distinctions, or search behaviour that don't exist as something people actually search for — kill the suggestion.

**Product capability (Middle/Bottom only)** — Middle and Bottom suggestions are product-proximate by definition: they imply Seobility does something specific. Before finalising a Middle or Bottom candidate, check that implied capability against `product-context/seobility_features.md` — do not infer capability from the topic name alone. Example of the failure this catches: a "page speed checker" Bottom angle implies Seobility measures page speed, but Seobility only measures server response time — a narrower, different capability. If a candidate overstates or misrepresents what the product actually does, kill it or reframe it to the capability Seobility genuinely has. This check does not apply to Top suggestions, which don't position the product.

---

## Step 4c-ii — SERP verification

Look up metrics for the best SERP-pattern candidate identified in Step 2 — a single specific phrase, not a request for new keyword ideas. Use `brief_dataforseo.sh`, which calls `keyword_overview` for the exact phrase given, not `sera_dataforseo.sh` (that script's `keyword_suggestions` call generates *new* variants from a seed, which is the wrong question here and is why this check used to come back empty almost every time):

```
./scripts/brief_dataforseo.sh "[best SERP-pattern candidate from Step 2]"
```

Returns `{ data_available, results: [{keyword, sv, kd, intent}] }` for that one phrase. Apply scoring rule: SV ≥ 150, KD ≤ 70.

**This is a verification check only — it never overrides the user's Primary KW and never re-prompts.**

- If the call surfaces a keyword with meaningfully higher SV or closer SERP-pattern alignment than the user's Primary KW within the same intent group, add a one-line note to the Flag column: *"SERP-check found: [keyword], SV [x], KD [x] — not applied."*
- If the call finds nothing that beats the Primary KW, add a one-line note to the Flag column: *"4c-ii verification: no qualifying result — check ran, nothing beat the Primary KW."* This distinguishes "checked and found nothing" from "didn't run."
- If the call fails or returns `data_available: false`, proceed silently — no note needed.

### SERP alignment tagging

Cross-reference the Primary KW against the H1 formats and patterns identified in Step 2:

- **SERP-aligned** — the keyword's modifier type, intent, and angle match a dominant H1 format from Step 2
- **SERP-adjacent** — plausible variant, not directly confirmed by Step 2 patterns

SERP alignment is a reference note only. If SERP-adjacent, note it in the explanation.

---

## Step 5 — Cannibalization check (H1 List)

Cross-references candidates against Seobility's published H1 list before generating final H1s in Step 6.

Read Seobility's published H1 list using the Google Drive MCP:

```
gdrive-read-file(fileId="1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc")
```

This returns the full GSheet including the H1 List tab, which contains Seobility's own published blog URLs and Topic/H1 values. Cross-reference every candidate H1 against the Topic/H1 column. This is always live — do not use the ahrefs_H1_list.csv file for this check.

**Hard block** — a Seobility post already exists with the same angle and primary keyword → drop the candidate. A hard block requires a direct angle match within the same seed KW cluster. Topical overlap from a piece that belongs to a different seed KW cluster is not a hard block.

**If a hard block occurs:** ask the user to supply a different Primary KW or adjust the angle before proceeding. Do not auto-generate a replacement.

**Soft flag (within-cluster sub-topic proximity)** — if an existing Seobility piece covers a sub-topic that sits within the same seed KW cluster as the candidate, keep the candidate but flag it. Surface the proximity in both the table Flag column and the explanation, and note how the candidate's angle should be scoped to avoid direct conflict.

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
- The Primary KW (or a close variant) must appear in every suggested H1. If it doesn't, the H1 fails the keyword-first rule regardless of how well it reflects the angle.
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

**For vertical suggestions**, use Approach A only (no performing URL angle to remap):

*Approach A — Seed KW + stage template*
Apply the format patterns for the confirmed funnel stage to the Primary KW. H1s should be built around the Primary KW — the Seed KW may appear naturally where the Primary KW contains it, but is not required.

**For horizontal suggestions**, apply a valid business type ICP or AI search platform angle from the expansion pools in Step 4a.

---

## Output

Present output in two parts: header block first, then the table, then explanations.

### Part 1 — Header block (outside table)

```
Primary KW: [value]
Seed KW: [value]
Seed KW type: [General SEO / Seobility feature / Named competitor / Named Seobility]
Recommended funnel: [Top / Middle / Bottom / Horizontal]
```

### Part 2 — Table

One row per suggested H1.

| Suggested H1 | Funnel | Direction | Primary KW | Flag |
|---|---|---|---|---|

**Column rules:**
- **Suggested H1:** the full H1 candidate
- **Funnel:** Top / Middle / Bottom of the suggested new piece
- **Direction:** Vertical or Horizontal
- **Primary KW:** the user-supplied Primary KW. Same across all rows.
- **Flag:** cannibalization soft flag, 4c-ii verification note, SERP-adjacent note, or intent-mismatch note if applicable, otherwise blank

Note: SV and KD columns are omitted in this variant — the user supplies their own research. If the user wishes to surface SV/KD in the output, they can supply the values at trigger time and Sera will include them in the header block and table.

### Part 3 — Explanations

After the table, list every suggested H1 with a one-line explanation:

- **[H1]** — [what the piece covers, who it targets, how Seobility enters, why it's writable, any cannibalization or intent flag]

---

## Step 7 — Topic selection and brief feed

After presenting the output table and explanations, ask:

> **Which topic do you want to brief?** Topic 1, Topic 2, or Topic 3?

Wait for the user's response.

Once a topic is chosen, check for any issues before outputting the brief feed. A "clean" output is one where the Primary KW, funnel stage, and H1 angle are all consistent with no unresolved flags. If anything is not clean, flag it and ask the user to decide before outputting the brief feed.

**Issues that require a flag and user decision:**

- Any unresolved intent mismatch from Step 4b that the user hasn't explicitly accepted
- Any other caveat in the explanation that would affect what the Brief skill receives as a blocking field

If the output is clean, output the brief feed immediately without asking for confirmation.

**Brief feed format:**

```
Brand: Seobility
H1: [chosen H1]
Seed KW: [Seed KW from header block]
Primary KW: [user-supplied Primary KW]
Funnel: [funnel stage of chosen H1]
Topic summary: [explanation text for the chosen H1 from Part 3, stripped of any caveat already resolved in Step 7]
```

After the brief feed block, add exactly this line:

`→ Ready for /brief — copy the block above and run /brief to generate the content brief.`

---

## Rules

- Cannot run without Primary KW and Seed KW. Ask for missing values before proceeding.
- Step 0 does not exist in this variant — do not attempt to fetch metadata from Notion.
- Always classify Seed KW type before running web lookup (Step 1 before Step 2)
- Always run a web lookup before generating candidates (Step 2)
- Always use the `web_search` tool directly for Step 2 web lookups. Do not use bash or any other method. If `web_search` is unavailable, stop and tell the user before proceeding. Never fall back to training knowledge and proceed silently.
- Web lookup must actively inform H1 format and keyword targets — not just validate the topic
- Always run cluster state check via Notion Content Library before deciding direction (Step 3 before Step 4). Notion search returns semantic results — always fetch each plausible result and confirm Seed KW matches exactly and Status = Published before counting as a confirmed sibling. Do not rely on search results alone. Exact-match counting stays the basis for ratio math, but review discarded near-misses for topical alias overlap and surface any found as a note — don't let a real sibling under an adjacent Seed KW label silently disappear.
- Step 4 direction is cluster-state-based, not performing-URL-based. Recommend funnel stage from ratio, then validate against Primary KW intent. Surface mismatches and wait for user decision before proceeding.
- Named competitor Seed KW → never Top, hard gate in Step 4. **Exception:** named AI search platforms referenced as themselves for AEO purposes (Google AI Overviews, ChatGPT, Perplexity) are not named-competitor topics — they follow AEO horizontal-expansion logic instead, and Top is valid for informational angles about the platform. Named SEO-tool competitors (Semrush, Ahrefs, Screaming Frog, etc.) remain hard-gated from Top.
- Named Seobility Seed KW → never Top, horizontal to adjacent use cases only
- **Product capability check (Step 4c, Middle/Bottom only):** before finalising a Middle or Bottom candidate, verify the implied capability against `product-context/seobility_features.md` — don't infer capability from the topic name alone. Kill or reframe any candidate that overstates what Seobility's product actually does.
- 2:1:1 is the target ratio (Top:Middle:Bottom) — not 1:2:1
- Horizontal expansion: business type angles and AI search angles only
- Business type ICP swap is only valid when it changes both the search query and the content meaningfully
- AI search horizontal: two valid patterns only — (1) same Seed KW shifted to AEO context, (2) named platform variants within the AEO cluster where the platform is load-bearing in the search query
- Never suggest optimizing existing content — that belongs to Dexter
- Step 4c (DataforSEO scoring and KW selection) does not run in this variant — Primary KW is already confirmed by the user
- 4c-ii (SERP verification) always fires after writability check — seeded with best SERP-pattern candidate from Step 2. Never overrides Primary KW. Never re-prompts.
- Hard cannibalization check via Google Drive MCP (Step 5) — read file ID `1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc` and cross-reference candidates against the Topic/H1 column. Seobility's own published content only. Hard block requires a direct angle match within the same seed KW cluster. Do not use the ahrefs_H1_list.csv for this check.
- If Step 5 hard-blocks, ask the user to supply a different Primary KW or adjust the angle. Do not auto-generate a replacement.
- Within-cluster sub-topic proximity is a soft flag, not a hard block — keep the candidate, surface in Flag column and explanation
- The Primary KW (or a close variant) must appear in every suggested H1
- Funnel stage language: Top / Middle / Bottom — never ToFu / MoFu / BoFu
- Output is a menu of suggestions — the user decides what to execute
- Step 7 runs after the output table and explanations — never before
- Brief feed output is blocked until all unresolved flags in Step 7 are resolved by the user
- Topic summary in the brief feed is the Part 3 explanation for the chosen H1, stripped of any caveat already resolved in Step 7

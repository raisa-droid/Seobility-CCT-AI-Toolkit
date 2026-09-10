# Sera URL Command

Invoke with: `/sera-url [URL]`

Generates content expansion suggestions for Seobility's English-language blog based on a performing URL. Sera fetches Seed KW, Primary KW, and funnel stage from Notion automatically — the user provides the URL only. Presents a ranked, intent-flagged keyword list for manual Primary KW selection, then outputs 2–3 candidate H1s with explanations and a ready-to-paste brief feed.

## Dependencies
- `scripts/sera_dataforseo.sh` — keyword scoring (Step 4c)
- `scripts/brief_dataforseo.sh` — single-phrase SERP verification (Step 4c-ii)
- Notion MCP — metadata fetch (Step 0) and cluster state check (Step 3)
- Google Drive MCP — H1 List cannibalization check (Step 5)
- `product-context/seobility_features.md` — product capability check for Middle/Bottom suggestions (Step 4b)

---

# Seobility's Sera — Content Suggestion Logic (Manual KW Selection)

## Purpose

Generate content expansion suggestions for Seobility's English-language blog based on a performing URL and its metadata. Sera fetches all required metadata from the Notion Content Library automatically — the tester provides the URL only.

**This variant's core difference from the standard Sera skill is Step 4c.** Instead of auto-selecting the highest-SV qualifying keyword as Primary KW, this version presents the full ranked, intent-flagged list and waits for the user to choose. Two downstream steps (5 and 7) have adjusted behavior as a consequence — see those sections. Two additional steps exist because this variant starts from a performing URL rather than a known Primary KW: **Step 4a** (intent cross-check, mirroring the Sera Keyword variant's Step 4b) and **Step 4d** (rebuilds the SERP gap from the confirmed Primary KW, since Step 2 in this variant runs against the performing URL's existing Primary KW, not the new one).

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

  **AI search platform exception:** Named AI search platforms referenced as themselves for AEO purposes (e.g. Google AI Overviews, ChatGPT, Perplexity) are not named-competitor topics, even though they're named third-party products — they follow the AEO horizontal-expansion logic in Step 4 instead, and Top is valid for informational angles about the platform itself (e.g. "What Are Google AI Overviews and How Do They Work"). This exception never applies to named SEO-tool competitors Seobility actually competes with (Semrush, Ahrefs, Screaming Frog, etc.) — those remain hard-gated from Top.

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

Record the SERP gap finding before proceeding — what the top results cover (dominant format, angle, content type) and what's structurally absent. This finding is for direction and topic validation only (Steps 2–4). **It is not the SERP gap field in the brief feed** — that gets rebuilt in Step 4d once the new piece's Primary KW is confirmed, since Step 2 runs against the performing URL's existing Primary KW, not the new one.

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

## Step 4a — Intent check against SERP

Cross-reference the direction recommended in Step 4 against the dominant search intent observed in Step 2's SERP results:

- `informational` intent → aligned with Top
- `commercial` / `investigational` intent → aligned with Middle
- `transactional` intent → aligned with Bottom

**If the recommended direction and the observed SERP intent are aligned:** proceed to Step 4b (writability & product capability check). No flag needed.

**If they are misaligned** (e.g. Step 4 recommends Top but the SERP intent is clearly commercial): surface the mismatch explicitly and ask the user to decide before proceeding:

> "The cluster/funnel logic suggests a **[recommended stage]** piece, but the SERP for this topic shows **[observed intent]** intent. Do you want to:
> (A) Proceed with **[recommended stage]** — I'll continue with the current direction, noting the intent mismatch.
> (B) Switch to **[intent-aligned stage]** — I'll re-run the direction logic for that stage instead."

Wait for the user's decision before continuing. The chosen stage is the confirmed target funnel for all downstream steps (4b, 4c, 6, 7).

---

## Step 4b — Writability & product capability check

Two independent checks must both pass before finalising any candidate:

**Writability** — can a writer produce this piece from real source material without hallucinating? If the topic requires claims about features, competitive distinctions, or search behaviour that don't exist as something people actually search for — kill the suggestion.

**Product capability (Middle/Bottom only)** — Middle and Bottom suggestions are product-proximate by definition: they imply Seobility does something specific. Before finalising a Middle or Bottom candidate, check that implied capability against `product-context/seobility_features.md` — do not infer capability from the topic name alone. Example of the failure this catches: a "page speed checker" Bottom angle implies Seobility measures page speed, but Seobility only measures server response time — a narrower, different capability. If a candidate overstates or misrepresents what the product actually does, kill it or reframe it to the capability Seobility genuinely has. This check does not apply to Top suggestions, which don't position the product.

---

## Step 4c — DataforSEO keyword scoring (manual selection)

Runs after direction is confirmed (Step 4) and writability is checked (Step 4b). Purpose: surface the full ranked, intent-flagged list of keyword variants and let the user choose the Primary KW — rather than auto-selecting the highest-SV option or pre-cutting the list to a narrow difficulty band. Output feeds directly into Step 5, but only after the user has made a choice and the verification check has completed.

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

### Filtering rule (SV is a floor; KD is not a gate)

1. Variants with SV < 150 are excluded (this is already applied inside the script — a floor, since near-zero volume isn't worth evaluating regardless of difficulty)
2. Drop obviously malformed/junk variants (e.g. spaced-out letter strings, garbled duplicates) — this is a data-quality filter, not a difficulty judgment, and happens before presentation
3. **Merge near-duplicates.** Variants that differ only by word order, singular/plural, or a filler word around the same core phrase (e.g. "page speed test" / "page speed tests" / "test page speed") describe the same underlying concept. Keep one representative per concept — the highest-SV variant — rather than listing every surface form. This is also a data-quality filter, not a difficulty judgment.
4. **Do not drop variants for KD > 70.** KD is a competitiveness signal, not a viability cutoff — a human may reasonably pick a KD 72 term the script would otherwise hide. Every remaining variant (up to 20) gets shown, banded by difficulty instead of gated by it (see below)

### Intent override for product/tool queries

Before grouping by intent, apply Step 1's product-query logic to each variant — do not trust DataforSEO's `main_intent` label on its own for this class of keyword. DataforSEO's label is reliable when a commercial signal word is present (e.g. "best," "vs," "alternative") but frequently mislabels bare tool-name queries as `informational` (e.g. "rank tracker," "backlink checker," "page speed test" routinely come back `informational` despite clearly implying tool evaluation).

Apply this override: if a variant matches a tool/product pattern — contains or effectively means checker, tracker, test, audit, software, tool, comparison, best, vs, alternative, or "top N" — treat it as Middle/Bottom-aligned intent for grouping purposes, regardless of the API's `main_intent` label. Note the override in the Intent column, e.g. `informational → commercial (tool query)`.

### Presenting the list for manual selection

Group the remaining variants by intent alignment against the target funnel stage from Step 4 (after applying the override above):

- `informational` → aligned with Top
- `commercial` / `investigational` → aligned with Middle
- `transactional` → aligned with Bottom

Within each intent group, band by KD instead of cutting:
- **Easier** — KD ≤ 70
- **Competitive** — KD 71–85
- **Hard** — KD 85+

Present two groups — **✓ Aligned with [target funnel stage]** and **✗ Other intent** — each sorted by SV descending within the group (band shown as a column, not used to exclude rows). Aligned rows are listed first.

```
**Choose a Primary KW for this [target funnel stage] piece.**

✓ Aligned with [target funnel stage]:

| Keyword | SV | KD | Band | Intent |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

✗ Other intent (shown for reference — may still be viable):

| Keyword | SV | KD | Band | Intent |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |
```

Wait for the user to name their chosen keyword.

**If the script returns zero variants at all (nothing meets the SV ≥ 150 floor):** state this plainly and ask the user to supply a Primary KW manually, or proceed without KW data per the fallback rule above.

**If variants exist but none are aligned with the target funnel stage** (the ✓ group is empty): say so explicitly — e.g. "No variants align with [target funnel stage] intent; showing the full list for reference." Then present the ✗ Other intent group alone (relabeled "All variants — none matched [target funnel stage] intent") and ask the user to either pick from it anyway, supply a Primary KW manually, or adjust the target funnel stage. Do not wait silently on a choice that isn't on the table.

### 4c-ii — Verification (always fires, after the user's choice)

Once the user has named their chosen keyword, always look up metrics for the best SERP-pattern candidate identified in Step 2 — a single specific phrase, not a request for new keyword ideas. Use `brief_dataforseo.sh`, which calls `keyword_overview` for the exact phrase given, not `sera_dataforseo.sh` (that script's `keyword_suggestions` call generates *new* variants from a seed, which is the wrong question here and is why this check used to come back empty almost every time):

```
./scripts/brief_dataforseo.sh "[best SERP-pattern candidate from Step 2]"
```

Returns `{ data_available, results: [{keyword, sv, kd, intent}] }` for that one phrase. Apply the SV ≥ 150 floor to the result (no KD cutoff).

**This is a verification check only — it never overrides the user's choice and never re-prompts.**

- If the call's result doesn't beat the user's chosen keyword on SV within the same intent alignment, proceed silently to Step 5. No note needed.
- If the call's result appears to be a closer SERP-pattern match or has meaningfully higher SV within the same intent group, add a one-line note to the Flag column and explanation: *"SERP-check found: [keyword], SV [x], KD [x] — not applied."* The user's original choice remains the confirmed Primary KW regardless.
- If the call fails, returns `data_available: false`, or the phrase falls below the SV floor, add a one-line note to the Flag column: *"4c-ii verification: no qualifying result — check ran, nothing beat the chosen keyword."* This distinguishes "checked and found nothing" from "didn't run" — do not simply proceed with no trace of the check having happened.

### SERP alignment tagging

Cross-reference the confirmed primary KW (the user's choice) against the patterns and H1 formats identified in Step 2:

- **SERP-aligned** — the keyword's modifier type, intent, and angle match a dominant H1 format from Step 2
- **SERP-adjacent** — plausible variant, not directly confirmed by Step 2 patterns

SERP alignment is a tiebreaker note only — it does not override the confirmed keyword. If SERP-adjacent, note the gap in the explanation.

---

## Step 4d — Rebuild SERP gap for the confirmed Primary KW

Step 2's SERP gap finding was captured for the performing URL's existing Primary KW, before the new piece's Primary KW was known — it exists to validate direction and topic (Steps 2–4), not to describe the SERP the new piece will actually compete in.

Once the Primary KW is confirmed in Step 4c (the user's chosen keyword, after 4c-ii verification), run a fresh web search using the confirmed Primary KW as the query. Always use the `web_search` tool directly — do not use bash or any other method, and never fall back to training knowledge.

Use this fresh lookup to record the SERP gap finding that goes into the brief feed: what the top-ranking results for the confirmed Primary KW cover (dominant format, angle, content type), and what's structurally absent — the specific territory the chosen H1 occupies that this SERP doesn't cover.

**This finding replaces Step 2's SERP gap for the brief feed at Step 7.** Step 2's original finding remains valid for what it was used for — direction and topic validation in Steps 2–4 — but must never be reused as the SERP gap source in the brief feed, since it reflects a different keyword's SERP.

If the fresh lookup is unavailable or fails, flag the SERP gap as unavailable in the brief feed rather than falling back to Step 2's finding.

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

**For vertical suggestions**, combine the best candidates from both approaches:

*Approach A — Primary KW + stage template*
Apply the format patterns for the target funnel stage to the confirmed Primary KW from Step 4c.

*Approach B — Performing URL angle remapped*
Take the performing URL's specific topic angle and shift the depth/intent to suit the target stage. Example: performing URL is "How to do a website audit" (Top) → Middle remap: "5 Best Website Audit Tools for Small Businesses."

**Primary KW is the expansion anchor.** All candidate H1s must be built around the confirmed Primary KW from Step 4c — not the performing URL's specific angle. The Seed KW may appear naturally where the Primary KW contains it, but is not required. The performing URL's angle is input context only: it determines funnel direction (Step 4), not topic scope. If Approach B produces a candidate that drifts away from the confirmed Primary KW, reframe it around the Primary KW.

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
SERP gap: [1–3 sentences. What the current top-ranking results cover — dominant format, angle, content type. Then what's structurally absent: the specific territory the chosen H1 occupies that the SERP doesn't. Source: Step 4d's fresh lookup for the confirmed Primary KW — never Step 2's finding.]
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
- Always run cluster state check via Notion Content Library before deciding direction (Step 3 before Step 4). Notion search returns semantic results — always fetch each plausible result and confirm Seed KW matches exactly and Status = Published before counting as a confirmed sibling. Do not rely on search results alone. Exact-match counting stays the basis for ratio math, but review discarded near-misses for topical alias overlap and surface any found as a note — don't let a real sibling under an adjacent Seed KW label silently disappear.
- **Primary KW is the expansion anchor** — all candidates must be built around the confirmed Primary KW from Step 4c, not the seed KW cluster in the abstract or the performing URL's specific angle. The performing URL's angle determines funnel direction only, not topic scope.
- Named competitor Seed KW → never Top, hard gate in Step 4. **Exception:** named AI search platforms referenced as themselves for AEO purposes (Google AI Overviews, ChatGPT, Perplexity) are not named-competitor topics — they follow AEO horizontal-expansion logic instead, and Top is valid for informational angles about the platform. Named SEO-tool competitors (Semrush, Ahrefs, Screaming Frog, etc.) remain hard-gated from Top.
- Named Seobility Seed KW → never Top, horizontal to adjacent use cases only
- **Product capability check (Step 4b, Middle/Bottom only):** before finalising a Middle or Bottom candidate, verify the implied capability against `product-context/seobility_features.md` — don't infer capability from the topic name alone. Kill or reframe any candidate that overstates what Seobility's product actually does.
- 2:1:1 is the target ratio (Top:Middle:Bottom) — not 1:2:1
- Horizontal expansion: business type angles and AI search angles only
- Business type ICP swap is only valid when it changes both the search query and the content meaningfully
- AI search horizontal: two valid patterns only — (1) same Seed KW shifted to AEO context, (2) named platform variants within the AEO cluster where the platform is load-bearing in the search query
- Never suggest optimizing existing content — that belongs to Dexter
- Always cross-check the Step 4 direction against the SERP intent observed in Step 2 (Step 4a) before the writability check. Surface any mismatch and wait for the user's decision — do not proceed silently.
- DataforSEO step (Step 4c) runs after direction is confirmed and writability is checked — never before Step 4
- DataforSEO script (Step 4c, keyword scoring from a seed): `./scripts/sera_dataforseo.sh "[Seed KW]"`
- DataforSEO script (Step 4c-ii, metrics for one exact phrase): `./scripts/brief_dataforseo.sh "[phrase]"` — never `sera_dataforseo.sh` here, since its `keyword_suggestions` call generates new variants rather than looking up the phrase given
- **DataforSEO scoring: SV ≥ 150 is a hard floor; KD is not a cutoff.** Junk/malformed and near-duplicate variants (differing only by word order, plural, or filler words) are merged/dropped as a data-quality filter, not a difficulty judgment. Up to 20 variants returned. Before grouping, apply Step 1's product-query override to correct DataforSEO's `main_intent` label for bare tool-name keywords (checker/tracker/test/audit/software/tool/vs/alternative/top N) that the API systematically mislabels as informational. No auto-winner — the full list is presented to the user, grouped by intent alignment (✓/✗ against target funnel stage), banded by KD (Easier ≤70 / Competitive 71–85 / Hard 85+), and sorted by SV descending within each group. Nothing that clears the SV floor is hidden from the user before they choose. If the ✓ group is empty (variants exist but none align with the target stage), say so explicitly and offer the full list for reference rather than waiting on an empty choice.
- The user selects the Primary KW manually from the presented list. Sera does not proceed to Step 5 until a choice is made.
- 4c-ii (verification call, seeded with Step 2's best SERP-pattern candidate) always fires after the user's choice — never before, never as a second decision gate. It only ever adds a reference note to the Flag column; it never overrides the user's pick and never re-prompts. Always add a Flag-column note whether or not it found anything, so "checked, found nothing" is distinguishable from "didn't run."
- SERP alignment from Step 2 is a tiebreaker note only — never overrides the user's chosen keyword
- Step 5 (cannibalization check) runs after the Primary KW is confirmed in Step 4c — never before
- If the DataforSEO script fails or times out, proceed without KW data and note "keyword data unavailable" — never halt
- Hard cannibalization check via Google Drive MCP (Step 5) — read file ID `1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc` and cross-reference candidates against the Topic/H1 column. Seobility's own published content only. Hard block requires a direct angle match within the same seed KW cluster. Topical overlap from a different seed KW cluster is not a hard block. Do not use the ahrefs_H1_list.csv for this check.
- **If Step 5 hard-blocks the chosen Primary KW, return to the Step 4c list and ask the user to pick a different keyword.** Do not auto-promote the next-highest-SV row. Re-run 4c-ii and Step 5 against the new choice.
- Within-cluster sub-topic proximity is a soft flag, not a hard block — keep the candidate, surface it in the Flag column and explanation, note how the angle should be scoped
- The Primary KW (or a close variant) must appear in every suggested H1
- Funnel stage language: Top / Middle / Bottom — never ToFu / MoFu / BoFu
- Output is a menu of suggestions — the user decides what to execute
- Step 7 runs after the output table and explanations — never before
- **Step 7's Primary KW intent-mismatch flag is suppressed in this variant** — the user already resolved intent tradeoffs manually at Step 4c. Only "Primary KW unavailable" and other blocking caveats still gate the brief feed at Step 7.
- Brief feed output is blocked until all remaining flags in Step 7 are resolved by the user
- Topic summary in the brief feed is the Part 3 explanation for the chosen H1, stripped of any Primary KW caveat that has already been resolved in Step 7
- SERP gap field is required in the brief feed. **Source it from Step 4d's fresh lookup for the confirmed Primary KW — never from Step 2.** Step 2's lookup runs against the performing URL's existing Primary KW and is for direction/topic validation only; reusing it as the brief feed's SERP gap describes the wrong keyword's SERP. Never generate the SERP gap from training knowledge. If Step 4d's lookup is unavailable or returned insufficient data, flag SERP gap as unavailable rather than inferring it or falling back to Step 2.
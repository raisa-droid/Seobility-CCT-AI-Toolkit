# /refresh design (Content Optimizer)

**Status:** building version 1 (optimize mode). All scripts and both command files built (2026-10-01). First `-analyze` test run 2026-10-01; output switched to the approval page 2026-10-02. `-fix` first run 2026-10-05 (full flow, analyze to Fix Doc, works end to end; fix quality still being tuned). Setup for a new user: `docs/refresh-setup.md`.
**Last updated:** 2026-09-30
**Users:** Jules and Raisa

---

## What /refresh is for

Seobility asked for a Content Optimizer for published blog posts. `/refresh` compares a post against what currently ranks on Google and gets cited by AI search, checks its facts and links, and then applies the fixes a human approves.

It is standalone: not part of the Sera → `/brief` → `/write` → `/score` chain. It leaves existing commands and skills unchanged and calls them only where noted.

Every post is treated as if it was written before `/write` existed, so all checks apply.

### In scope
- SEO and AEO signals (keyword placement, metadata, headings, answer structure, internal links, anchors, product link caps)
- Content refresh (missing topics, entities, formats, FAQs, info gain)
- Fact and link check (dead links, outdated claims, Seobility and third-party pricing and features)

### Out of scope
- **Editorial changes to existing copy:** em dashes, UK vs US spelling, tone. New copy follows the style rules; old copy is left alone unless a finding targets it.
- **Technical SEO:** schema, image alt text, page speed, and so on.
- **URL slug changes.** They need a redirect, which is a dev task.
- **Scoring.** Replaced by finding counts (see Analyze Doc).
- **Showing ranking positions.** Our rank is collected but never shown in the Doc or in chat. It only sets the performance tier (see Findings model). Use GSC to track before vs after.

---

## Commands

```
/refresh-analyze [blog URL] primary kw: … secondary kw: … contextual kw: …
/refresh-fix [Analyze Doc link]
```

- Primary keyword is required. Secondary and contextual keywords are optional.
- URLs must contain `/blog`. Anything else is rejected.
- A primary keyword under 3 words gets a head-term warning (the user can continue).

---

## Modes

The mode is set by **whether the primary keyword changes**, not by how much text changes.

| | Optimize (version 1) | Retarget (after version 1) |
|---|---|---|
| Trigger | Primary KW matches Notion | Primary KW differs from Notion (a related angle) |
| Post's frame | Stays the same | Changes, e.g. "javascript seo problems" → "how to make javascript seo-friendly" |
| New sections | Yes | Yes |
| Rewriting | Only what a finding targets | Whole sections, via the section map |
| Cut or merge sections | Only when a finding calls for it | Planned in the section map |
| Extra steps | None | SERP overlap check (Stop 1), section map (Stop 4) |

Retarget is described at the end. Everything else applies to both modes.

---

## /refresh-analyze

| # | Step | Done by | Stop |
|---|---|---|---|
| 1 | Check the input | Claude | |
| 2 | Notion lookup | Claude + Notion | **STOP 1: keyword check** (only when something is flagged) |
| 3 | Crawl the post, save a snapshot | Script | |
| 4a | Build the 3 AEO phrasings | Claude | **STOP 2: H1, primary KW, phrasings** |
| 4b | Searches: SERP + AEO | Scripts | **STOP 3: competitor lists** |
| 5 | Fetch and strip competitor pages | Script | |
| 6 | Strategy | Claude | **STOP 4: H1, funnel** |
| 7 | Golden entity map | Claude (skill) | |
| 8 | Fact and link check | Script + Gemini + Claude | |
| 9 | Judging: write the findings | Claude | |
| 10 | Create `Analyze_[H1]`, report token use for this `-analyze` run | Claude + Drive | **Jules fills the Decision column** |

### Step 2: Notion lookup (STOP 1)

Content Library `collection://344eba87-0b26-817b-980a-000b96d30f1d`, matched on the `URL` field by **URL slug** (so `https`/`www`/trailing-slash differences don't break it).

Fields used:
- `Primary KW`: compared with the user's primary keyword. If they differ, show both and wait for confirmation. (In version 1, a changed keyword means stopping and telling the user retarget mode isn't built yet.)
- `Funnel`: our side of the funnel mismatch check at Stop 4.
- Cannibalization: search the database for other rows whose `Primary KW` matches the user's primary keyword.

Not used: `Not Evergreen`.

If the post isn't in the library, say so and continue.

**No flags, no stop** (changed 2026-10-01 after the first test run): when the keyword matches, there's no cannibalization, the post is in the library and there's no head-term warning, Stop 1 is a one-line note and the run continues.

### Step 3: Crawl

A script, not WebFetch (WebFetch returns a summary, not the exact text). The Seobility blog uses one template, so the script targets its article container.

Captures:
- H1, title tag, meta description
- Heading outline, with a paragraph ID (P1, P2, …) for every block, so findings can say exactly where
- Every link: anchor text, href, internal or external
- Published and updated dates
- In-body CTA boxes are included. Page heading, nav, sidebar, related posts and author bio are excluded.

The snapshot is saved in a git-ignored `.refresh-cache/` at the repo root. `-fix` edits this exact text.

### Step 4: Phrasings and searches (STOP 2, STOP 3)

All searches: US Google, English (`location_code` 2840, `language_code` en). Searches use the **primary keyword, not the H1**: the keyword is what people type, and the H1 may change at Stop 4.

**SEO set:** DataForSEO SERP (organic live advanced, the endpoint `/brief` already uses) for the primary keyword, depth 10, **called 7 times in parallel**, plus a stored-snapshot tiebreaker.
- Organic top 3 articles. Skip Reddit, YouTube, forums, seobility.net and non-article pages; take the next result instead. The script skips by URL; non-article pages with normal-looking URLs (tool pages, dashboards) are caught by Claude at Stop 3 and swapped for a backup.
- Google AI Overview sources, when the SERP has an AI Overview (same call, no extra cost).
- PAA questions and related searches (for the FAQ refresh).
- Our post's rank in each result set (internal only; sets the performance tier). If the agreeing calls differ by a place or two, the best rank counts, so an edge case gets the lighter tier.
- **Why 7 calls** (tested 2026-09-30, 105 calls over 3 keywords): about half of all live calls return a different, weaker result set for the same keyword seconds apart, sharing 0–1 of their top 10 with the real set. Bad calls come in streaks. In 15 batches, the first 5 calls missed the real set once; 7 calls never did. The script groups calls whose top 10 share at least 5 URLs.
- **Tiebreaker:** one call to DataForSEO Labs historical SERPs (stored Google snapshots, weeks or months old). Too old to be the competitor list, but every tested snapshot matched the real set (4–8 of 10 shared) and never the bad one (0–1). The live set sharing the most with the latest snapshot (at least 3) is recommended. **No majority vote:** the real set was the minority in several runs.
  - No live set matches the snapshot: 7 more calls, once. Still none: flagged at Stop 3 as `no_match`.
  - No stored snapshot for the keyword: Claude recommends a set by relevance (`no_snapshot`).
  - Failed calls are skipped; the run only fails if every call fails.
- Cost: $0.002 per live call (depth 5 costs the same as depth 10) + $0.0005 for the snapshot = ~$0.015 per run, ~$0.03 with the retry. ~20 seconds (~40 with the retry).

**AEO set:** Gemini grounded search (via the webhook, `tools: [{googleSearch:{}}]`) on 3 phrasings, all built from the primary keyword:
1. **As typed:** the primary keyword exactly, lowercase, no punctuation. "javascript seo problems"
2. **Plain question:** the question a person would type into an AI assistant, keeping the keyword's words. "What are common JavaScript SEO problems?" If the keyword is already a question ("how fast should a website load"), ask the same thing in different words ("What is a good load time for a website?"), so phrasings 1 and 2 aren't the same search.
3. **Conversational:** 1–2 sentences, first person: the reader's problem, then the question. "Google isn't indexing half my React pages. What JavaScript SEO problems could cause that?"
   - Problem source: the "Core Issue" line of the post's "In this post" box if there is one, otherwise the intro paragraphs before the first H2.
   - No persona ("I'm an SEO manager"), no brand names, nothing from the post's answer (not "under 2 seconds"), under 40 words.
   - If the intro has no clear problem, fall back to a second plain question worded differently from phrasing 2.

Tested 2026-10-01 on 3 posts (how fast should a website load, google core update, seo for new websites): every top 3 page was cited across all 3 phrasings, no calls failed, every link resolved.

- **Each phrasing runs 5 times** (15 calls in parallel, ~20 seconds). Tested 2026-09-30: one run of a question cites 11–20 sites with little overlap between runs. With 3 runs per phrasing the top 3 changed on every repeat; with 5 it was identical on all 3 repeats.
- Gemini gets today's date as a system instruction, like real AI search has. Without it, it searched for "2023" results.
- Gemini's citation links are redirect URLs; a script resolves them to the real pages.
- Ranking: cited in more phrasings (of 3) first, then in more runs (of 15), then more answer sentences supported. Take the top 3, with the same skip rules as the SEO set; the next 5 are backups for Stop 3.
- The answers themselves are saved to the cache, so Claude can read what AI search says about the topic.
- Cost: ~20k output tokens per run (~$0.05 on Gemini 2.5 Flash) plus grounding, which depends on the webhook's Gemini plan.

**Stop 2** (before any search runs) shows the H1, the primary keyword and the 3 phrasings, so the user can edit the phrasings before the AEO script spends 15 calls on them. **Stop 3** shows both competitor lists; the user can swap competitors before anything is fetched. The command says up front that the searches take about 40 seconds (in the first test run, the quiet wait looked like a hang and the run was stopped). If the SERP calls split, Stop 3 shows the recommended set (the one matching the stored snapshot) first, with the other sets listed below it, and the user confirms. With `no_snapshot`, Claude recommends the set whose pages answer the keyword. With `no_match`, Stop 3 says none of the live sets matched Google's stored results and asks the user to pick or check the keyword. PAA, AI Overview sources and the performance tier come from the confirmed set. Picking the right set matters: in the bad set our post is usually missing, which would wrongly put it in "needs content".

To check at build time: DataForSEO content parsing (as an alternative to our own page stripper) and Google AI Mode results. The webhook passes any endpoint through.

### Step 5: Fetch and strip competitors

A script fetches each competitor page and keeps the outline, article text, formats used (tables, steps, lists) and FAQs. Nav, footer and sidebars are dropped.

- **Own stripper first, DataForSEO content parsing as fallback** (decided 2026-10-01). Content parsing is cheap ($0.00015/page) but flattens lists into lines, so it can't tell us whether a competitor uses lists or steps. Our stripper keeps them. The fallback runs when a page is blocked, errors, or yields under 300 words; those pages report list counts as unknown.
- Works on any site: noise is dropped by tag, role and class/id, then the article root is the deepest element still holding 80% of the text.
- Pages are fetched with curl (the Mac's system Python is too old for some sites' TLS).
- FAQs are tagged by source: a visible FAQ section or `<details>` questions (`page`), or FAQPage schema (`schema`). Schema FAQs often just repeat the article's headings, which matters for the FAQ duplication check.
- Tested 2026-10-01 on 15 pages across 3 keywords: all extracted, including WordPress, Elementor, Google docs and a status dashboard. Small leftovers like a product CTA or an author bio can stay in; they don't affect topic comparison.

### Step 6: Strategy (STOP 4)

Shows (format set 2026-10-01 after the first test run, no extra commentary):
- A `Page · Meta title` table (ours + competitors, no H1 column), then "keep as is" or 2–3 suggested H1s with a one-line reason each
- A `Page · Funnel` table: ours (Notion; if empty or `N/A`, Claude classifies the post) and each competitor's (Claude classifies from the page). No mention of product link caps.
- A `Page · Format · Words · Tables · FAQs · Notes` table, plus at most one line on the pattern

**Funnel mismatch:** the user decides whether to move to the competitors' funnel stage or stay.
- Change: gaps specific to that stage (tool comparisons, "how to choose") become findings.
- Stay: those gaps are excluded, and the Analyze Doc lists what was excluded and why.

Product link caps always apply, using the chosen funnel: Top 1, Middle 2, Bottom 2 body product links (not counting a dedicated Seobility section or the closing CTA).

**Funnel switch → section map.** If the user switches funnel, Stop 4 also shows a section map (see below) before any findings are made. If the funnel stays, there's no map.

**Protect tier (rank 1–3):** no suggested H1s and no funnel switch (a switch triggers the section map, which is a restructure). Stop 4 shows "keep as is" for both and moves on. A funnel mismatch is noted but not acted on.

Everything after this stop uses the confirmed H1 and funnel.

### Section map (funnel switch in optimize mode; always in retarget mode)

Approved in chat at Stop 4. Findings build on the approved map, and findings for cut sections are dropped.

Columns: `H level · Current section · Decision · Why`

- Rows follow the **current** order so the original structure stays visible. New sections are inserted where they would go; moved sections say where to ("Move → after [section]").
- New rows: H level shows e.g. `H2 (new)`, and the heading copy is in *italics*.
- Decisions: keep, rewrite, merge, cut, move, new.

| H level | Current section | Decision | Why |
|---|---|---|---|
| H2 | What Is JavaScript SEO | Rewrite, shorter | Middle-funnel readers know the basics |
| H2 | 5 Common Problems | Keep | Core of the post |
| H2 | History of JS Crawling | Cut | No value at this funnel stage |
| H2 (new) | *How to Choose a Rendering Solution* | New | 3 of 3 competitors cover it |

### Step 7: Golden entity map

Runs `skills/golden-entity-map.md` unchanged, with:
- Target topic: the confirmed H1. Brand: Seobility.
- Optional inputs: our crawled post and the fetched competitor pages. The skill's own research step uses these and doesn't run new web searches, so research isn't done twice. The skill already checks `novel_information_gain` against competitor coverage, so no extra check is needed.

Entity rule from `/brief` 1c: the SERP format decides what counts as an entity. In listicles and comparisons, tool names count. In other formats, only concepts, methods, standards and technical terms.

### Step 8: Fact and link check

Always runs.

- **Links:** every link's status. Dead links, redirects, and redirects that land on a homepage (soft 404) are flagged.
  - Verdicts from `refresh_links.py`: `dead` (4xx, 5xx, DNS failure, timeout), `soft_404` (redirect from a deep page to a homepage or language root, or a page titled "404"/"not found"), `redirect` (`minor` = same page after http→https/www/slash or twitter→x; `moved` = different URL), `unverified`, `ok`.
  - **Unverified ≠ dead.** Sites that block bots (403/429) get a second check through DataForSEO's crawler ($0.00015/link). Sites that block that too stay `unverified` and are never reported as dead links. Tested 2026-10-01: searchengineland.com blocks both (18 links in the core updates post); DataForSEO got through for 3 other blocked sites.
  - Minor redirects are not findings; `-fix` can quietly update them to the final URL.
- **Dirty links:** affiliate links (affiliate parameters and networks) and other tracking parameters are findings. AI-tool tracking tags (e.g. `utm_source=chatgpt.com`, also Perplexity, Copilot and similar) are stripped silently by `-fix`.
  - `affiliate` = known networks (Amazon `tag=`, ShareASale, Awin, CJ, Impact, …) or affiliate-only parameters. `possible_affiliate` = generic parameters like `?ref=` or `?via=` that can also be plain referral labels (`?ref=producthunt`); Claude judges those. Every tracking and AI-tag hit comes with a clean URL.
- **Claims:** stats and dated claims older than 3 years are flagged. Outdated references too (deprecated tools, old Google updates described as new).
- **Outdated years** in the H1, title or meta (e.g. "SEO Trends 2023").
- **Seobility pricing and features:** checked against `product-context/seobility_pricing.md` and `seobility_features.md`.
- **Third-party pricing and features:** checked with grounded Gemini against the live pricing page.
  - `refresh_facts.sh`: Claude pulls the checkable third-party claims from the snapshot (pricing, features, specs, stats, references) into a claims file; the script checks each with grounded Gemini, **2 runs per claim**, and returns a verdict, what current sources say, a suggested correction and the real source URLs (from grounding metadata, not URLs Gemini writes).
  - Verdicts: `correct`, `outdated`, `wrong` (wrong and outdated agree with each other), `disputed` (some runs say correct, others say it needs a fix → `[TODO · VERIFY: …]`), `unverifiable` (no run could confirm it, or no live source was cited).
  - Seobility claims are not sent to Gemini; Claude checks them against `product-context/`.
  - Tested 2026-10-01 on the pagespeed post (6 real claims + 1 made-up Pingdom price): 5 full repeats gave identical verdicts, even at 1 run per claim. It caught a real error: the post's INP definition ("a user's first interaction") describes FID; INP covers all interactions. The test price ($5/month) came back outdated with the monthly and annual price kept apart, as the pricing rules require. Gemini cited Pingdom's own pricing page, but that page loads its prices with JavaScript, so the figure couldn't be confirmed independently.

**Claim extraction rule** (added 2026-10-05 after a Sonnet run extracted 6 claims and missed the wrong INP definition): Claude goes through the snapshot block by block and takes every sentence that states a fact about something outside Seobility. Definitions of metrics, tools, standards and terms (`kind: definition`) and thresholds are always included. `refresh_facts.sh` checks a definition against the official documentation, including scope and threshold.

Pricing rules for both:
- Expand inherited tiers: "Everything in Starter, plus X" = Starter's full list + X.
- Don't mix monthly and annual prices.
- Match currencies.
- Anything that can't be confirmed from the live source becomes a `[TODO · VERIFY: …]` placeholder, never a guessed correction.

### Step 9: Judging

Claude does all judging. Gemini is only used where live search is needed (the AEO set and third-party fact checks). Scripts do the mechanical work.

**Gap rule:** a topic is a gap when 2 of 3 pages in a set cover it and our post doesn't.
- Organic set → SEO gap. AI-cited set → AEO gap.
- A gap in both sets is listed once, in the SEO table, marked "also AEO" (SEO is the foundation of AEO).
- A missing entity that's also a competitor gap is one finding, in the Entities table, with the overlap in the Problem text ("Missing. Also covered by 2 of 3 top results.").

Each finding gets a **fix type** and a **priority** (or Must).

---

## Findings model

### Fix types

Findings are sorted by the fix they need, not by discipline. `-fix` applies them in this order:

1. **Add or restructure:** new sections, FAQ refresh, prose → table or steps, reordering sections.
2. **Edit in place:** keyword placement, title and meta, heading rewording, direct answers, naming or explaining entities.
3. **Replace or verify:** outdated stats, dead links, pricing and features.

New sections are added first so later edits (keyword placement, links) run on the final text.

### Priority

- **Must:** `-fix` won't run until every Must is `Y` (info gain: at least one `Y`).
  - Info gain angles (Jules picks at least one)
  - FAQ refresh (every run, see below)
  - Wrong Seobility pricing or features
  - Dead links
- **High / Medium / Low:** everything else, by impact.

The performance tier changes this list (below).

### Performance tier (internal)

Set by our post's rank for the primary keyword in the confirmed SERP set (Step 4). Never shown to users: the Doc just contains the findings that fit the tier. Written to the run's cache (`serp.json`) so Raisa can check it when a run looks off.

| Tier | Rank | Work | Effect |
|---|---|---|---|
| **Protect** | 1–3 | Maintenance: keep it correct and current | See below |
| **Striking distance** | 4–10 | Middle: on-page fixes | On-page findings go up one level: title, meta, keyword in intro and headings, heading rewording, one or two missing sections |
| **Needs content** | 11+ or not found | Major: our coverage is likely narrower or shallower than the top performers | Content gaps, missing entities and info gain go up one level |

"Up one level": Low → Medium → High. High stays High. Must is never affected by the tier.

**Protect tier rules:**
- **Must:** FAQ refresh, dead links, and the full fact check: Seobility pricing and features, plus third-party pricing, features, studies and stats. Outdated claims that would normally be Fact & link findings with a priority become Must.
- **Info gain is not Must.** It's optional (High), limited to a paragraph or an H3, never a new H2. `-fix` runs without an info gain `Y`.
- **Not touched:** structure (no new H2s, cuts, merges or reordering), keyword positioning, H1, title and meta description. These findings aren't made.
- **One exception:** an outdated year in the H1, title or meta ("SEO Tips 2023") is still flagged. It's a factual fix, not re-optimizing the keyword.
- **Other minor suggestions are allowed:** a missing entity named in an existing sentence (ladder level 1–2), a thin entity explained, a direct answer under a question heading, a missing internal link.

### What each table checks

| Table | Checks |
|---|---|
| **SEO** | Topic gaps (organic set); format gaps (tables, steps); exactly one H1, containing the primary keyword; title tag 50–60 characters with the keyword near the front; meta description 120–155 characters; keyword in intro and headings; keyword stuffing (flag existing, and a ceiling for `-fix` when placing keywords); anchors under 3 words; product link caps; missing internal links (from the Sitemap Cache); section order vs. competitors (2 of 3 pattern) |
| **AEO** | Topic gaps (AI-cited set); clear definition near the top; vague headings; no direct answer under a question heading; sections that don't stand alone (vague "this"/"it"); key takeaways block; enumerable content written as prose (→ list); answer the H1 early (sections that answer the H1 first, background later, closing section, FAQs last). New sections follow the same order rule |
| **Entities** | Missing and thin `must_include` entities; `must_avoid` entities found in the post. Extra **Status** column: Missing / Thin / Avoid |
| **Fact & link** | Links (redirects, soft 404s, dirty links), outdated claims and references, outdated years in H1/title/meta, third-party pricing and features (Seobility errors and dead links go in Must) |

**Heading case matches the post** (decided 2026-10-02 after the first `-fix` run mixed title-case new headings into a sentence-case post): new, renamed and suggested headings follow the case most of the post's existing headings use. `/write`'s title case rule doesn't apply to refreshes. Untouched headings keep their case.

**Keyword placement uses close variants** (decided 2026-10-01 after the first test run, which wrongly flagged "How fast should your website load?" for the keyword "how fast should a website load"): swapped articles or pronouns, plurals, reordered words and words in between all count as containing the keyword. Only missing core words are flagged. Casing of existing headings is editorial and out of scope.

### Entity logic

Borrowed from `/brief` (1c, 1d, placement rules) and `/write` (entity rules).

Each `must_include` entity is in one of three states:
- **Covered:** named and explained. No finding.
- **Thin:** named but unexplained. Edit-in-place finding: explain it in plain words and tie it to what the reader does. (May be dropped later if it drifts into editorial.)
- **Missing:** placed using the ladder below.

Placement ladder: the smallest change that covers the entity properly.

| Level | When | Fix type |
|---|---|---|
| 1. Name it in an existing sentence | The post discusses the concept without naming it | Edit in place |
| 2. Add a paragraph or bullet | An existing section is the natural home but doesn't cover it | Edit in place |
| 3. New H3 under an existing H2 | Needs its own explanation, belongs to an existing section | Add/restructure |
| 4. New H2 | A distinct concept with no home in the post | Add/restructure |

Rules:
- Each entity is placed in exactly one section, where it's most central. Broad entities go under the first H2 where they fit.
- The entity's `context` becomes the fix direction, never copied verbatim.
- Priority from `semantic_weight`: 9–10 High, 6–8 Medium.

Other uses of the entity map:
- **Writing new sections:** `-fix` uses each section's entities and their `context` lines as direction.
- **FAQs:** answers name relevant entities, only where it reads naturally.
- **Guardrail for new copy:** `must_avoid` terms are kept out of anything `-fix` writes.
- **Contextual keywords:** if the user gives none, the top-weighted entities fill in.
- **Key takeaways block:** if one is added, it names the top-weighted entities.

Not used for: internal links, or forcing entity names into headings.

### FAQ refresh (Must, every run)

Every Analyze Doc has one FAQ refresh item in Must, so every `-fix` refreshes the FAQs. It gets its own small table in the Must section, one row per question:

`Question · Action · Reason · Source · Decision`

**Sources, in order:**
1. **Fit with the post (gate):** the question must be about this post's topic and not already answered in the body.
2. **People Also Ask:** the demand evidence and main source (from the Step 4 SERP call, no extra cost). If the SERP has no PAA, fall back to related searches, then to questions from the post's own content.
3. **Our own angle:** questions from the post's info gain angle or entities, to fill remaining slots with something competitors can't match.
4. **Competitor FAQs are not a source.** They're only a check: if our block would mostly repeat a competitor's, flag it and prefer questions competitors don't answer.

Questions from AI-cited pages are not used.

**Writing quality never decides whether a question stays.** Every kept question is rewritten anyway. Fit and demand decide.

| Action | When |
|---|---|
| Keep (rewrite) | Fits the post and has PAA demand, or comes from our own angle. At minimum the answer is paraphrased; the question wording changes only if the PAA version is a closer match. |
| Replace | Fails the fit gate or has no demand, and a stronger question is available |
| Cut | Fails the fit gate and nothing better is available, or the block is over 6 |
| Add | A PAA or own-angle question the post doesn't cover, up to 6 |

- **No FAQ block:** a new block is proposed from the same sources.
- **Size:** 3–6 questions. `-fix` checks that the approved plan lands in that range.
- **Placement:** the last section, after the closing section, headed "FAQs About [Primary KW]" (same as `/write`). An FAQ block elsewhere in the post moves there.
- **Answer standard** (from Ane's page-faq-scorecard, no score, no schema): 40–60 words, direct answer first, specific facts, entities named only where natural, no repeating the body.

### Info gain placement

Proposed in `-analyze`, not decided in `-fix`:
- Uses the angle's `context` line and our outline.
- H2 vs H3 rule from `/brief` 1d: H2 if it's a distinct concept the reader needs on its own; H3 if it deepens an existing H2.
- The Where column says exactly where (e.g. "new H2 after Rendering Problems", "expand P14").
- Jules can override in the Decision cell. `-fix` follows the approved placement.

---

## Approval page (replaces the Analyze Doc, decided 2026-10-02)

The first test run produced a 25-page Analyze Doc with a Y/n cell for each of 33 findings. Replaced in two steps:

1. **Fewer, grouped decisions** (A+B+C): findings go into buckets. **Decide** (info gain angles, FAQ questions, anything that adds, cuts, merges or moves a section, adds a table, changes the H1, title or meta, or renames a heading) needs a Yes/No. **Applied** (edits in place: keyword placement, direct answers, entities, internal links, anchors, typos, moved redirects, sourced corrections, verify placeholders) is applied unless skipped. **Required** Applied items (dead links, wrong Seobility facts; the full fact check in the protect tier) can't be skipped. **For info** needs nothing. Findings that touch the same section are merged into one section package. Details (full problem and fix) stay available but out of the way.
2. **An interactive approval page instead of a Doc** (option F): a private claude.ai artifact built from the reusable `templates/refresh-approval.html`. One card per item, grouped and tinted by section (info gain violet, FAQ blue, other changes teal, applied sand); the card's left edge shows the decision (green Yes, red No, amber open). A sticky status bar mirrors the `-fix` gate and shows the `/refresh-fix` command when everything passes. Follows the viewer's light or dark theme.

**How it works:** `-analyze` writes `.refresh-cache/[slug]/findings.json` (meta, top performers, notes, items with id, bucket, section, title, why, details, checklist tags), copies the template with the post's title, publishes it (db capability, writes limited to owner and editors) and loads the findings with `ArtifactData set` from the file path. Decisions are saved per item in the page's `decisions` collection. `-fix` lists that collection. Publishing and loading by file path keep the per-run token cost below the Doc's (no HTML passed inline, no full-Doc read-back).

**Drive record:** the Fix Doc starts with an approval summary (applied, skipped, couldn't apply) and links the approval page. `-analyze` writes nothing to Drive.

Same person runs `-analyze` and `-fix` (no hand-off to Jules), so a claude.ai page is fine. Options considered and dropped: deciding in chat (D), commenting on drafted text in a preview Doc (E).

## Analyze Doc (superseded by the approval page, kept for history)

Created in the refresh folder `1CTthW4EQ9qMEMAh1_xbhyB8GVv3InORS`. The H1 is cut when the name gets too long.

1. **Header:** URL, keywords, mode, date checked
2. **Finding counts** (Must not counted): "SEO: 4 High, 3 Medium · AEO: 1 High, 2 Medium · Entities: 3 High, 2 Medium · Fact & link: 2 High"
3. **Top performers:** organic top 3, AI-cited top 3, AI Overview sources if present. Title, URL, set.
4. **Excluded gaps** (only if the funnel was kept despite a mismatch)
5. **Must**
6. **SEO**
7. **AEO**
8. **Entities**
9. **Fact & link**

Every findings table has the columns:

`ID · Fix type · Where · Problem · Suggested fix · Priority · Decision`

- IDs run continuously across tables (F1, F2, …).
- **Where** quotes the text or names the paragraph ID.
- **Suggested fix** uses BEFORE → AFTER only where the exact wording is the fix and the text is short: always for title tag, meta description, H1 and headings; sometimes for a single sentence (keyword or entity added); never for anything longer. BEFORE is capped at one sentence. Everything else gets a one-line direction, and `-fix` writes the text.
- **Decision:** `Y`, `n`, blank (= not approved), or `Y` plus a note (the note becomes an instruction for `-fix`).
- **FAQ rows** each need `Y` or `n` (no blanks): `Y` = do the action, `n` on Keep = leave that question and answer as they are, `n` on Replace/Cut/Add = don't do it. `-fix` checks that the result lands at 3–6 questions.
- No `|` characters in any cell.

**Tested 2026-09-29:** HTML tables imported through the Drive connector read back cleanly with `read_file_content` (rows, blanks, case, notes intact). The markdown export breaks on `|` in a cell, so `-fix` uses `read_file_content`.

---

## /refresh-fix

| # | Step | Done by | Stop |
|---|---|---|---|
| 1 | Read the Decision column. Every Must `Y`? At least one info gain `Y` (only when the Must table has info gain rows; protect-tier Docs don't)? | Claude + Drive | **Stops if not** |
| 2 | Compare the snapshot with the live page | Script | **Warns if the page changed** |
| 3 | Apply approved fixes: add/restructure → edit in place → replace/verify | Claude | |
| 4 | Create `Fix_[H1]` | Claude + Drive | |
| 5 | Report token use for this `-fix` run | Claude | |

**Rules for new copy** (new sections, rewritten FAQs, rewritten sentences):
- `product-context/Seobility_tone_of_voice.md` and `/write`'s style rules (US spelling, no em dashes, title case headings, anchors of 3+ words)
- `/write`'s entity rules: explain on first use, tie to an action or outcome, exact names for branded entities
- Product mentions through `skills/product-plug.md`, with caps from the chosen funnel
- Placeholders: `[TODO · TYPE: message]` (VERIFY, TEAM, SCREENSHOT), highlighted `#f1fa8c`
- Parser rules (from Ane's seo-check-for-parsers), only in definitions, FAQ answers and product sentences: name the subject; numbers and proper nouns over adjectives; one claim per sentence. In Seobility sentences, `product-plug.md` wins (no prices or plan details in soft mentions).

Existing copy that no finding targets stays exactly as crawled, except for silent fixes.

**Silent fixes** (applied without a finding, not logged):
- Paragraphs over 4 sentences split at natural break points, no words changed
- AI-tool tracking tags removed from links (same destination)

### Fix Doc: `Fix_[H1]`

1. H1 (as a heading)
2. URL slug
3. Update date: YYYY-MM-DD (the date `-fix` runs)
4. Title tag and meta description, always included, each marked changed or unchanged
5. Link to the Analyze Doc
6. Divider
7. Change checklist
8. Divider
9. The clean edited copy, with new sections highlighted (not yellow, so they don't mix with placeholders)

**Change checklist** (ticked or blank, section names where useful):
- [ ] Primary keyword changed
- [ ] Funnel changed
- [ ] H1 changed
- [ ] Title tag / meta description changed
- [ ] New sections added
- [ ] Sections removed or merged
- [ ] Sections restructured or reordered
- [ ] FAQs refreshed
- [ ] Key takeaways / summary block added
- [ ] Missing entities added
- [ ] Outdated info updated
- [ ] Links updated

Silent fixes are not logged on the checklist.

---

## Retarget mode (after version 1)

Same commands, stops and Docs. Differences:

- **Step 2 (Stop 1):** the keyword differs from Notion, so retarget mode starts. Stop 1 also shows:
  - Search volume for the old and new keywords (`brief_dataforseo.sh`)
  - SERP overlap: URLs shared between the two keywords' top 10. Low overlap is **flagged**; the user decides. Threshold parked until version 1 works.
  - Cannibalization check on the new keyword
  - The old primary keyword becomes a secondary keyword by default (the user can remove it).
- **Step 4:** all searches run on the new keyword.
- **Step 6 (Stop 4):** always shows the **section map** (format above).
- **Step 9:** findings build on the approved map. Findings for cut sections are dropped. Line-level findings work as in optimize mode.
- **`-fix`:** rewrites and reorganizes sections per the map. The checklist ticks "Primary keyword changed".

---

## Cost (measured 2026-10-02, Opus 5.5, decided 2026-10-05)

First full cycle on the pagespeed post (1,408 words, 5 competitor pages), from the saved transcripts at API list prices ($4 in, $20 out, cache write 1h $8, cache read $0.20 per million tokens): `-analyze` $3.30 (29 turns), `-fix` $2.63 (27 turns), external APIs about $0.09. About $6 per cycle. On a Team plan this was ~11% of the 5-hour limit, not billed per token.

Where it went: about 40% is the fixed baseline (Claude Code's own ~60k tokens of tools, connectors and skills plus the command file, written once and re-read every turn); about 28% is Claude's output (thinking is about half of it; in `-fix`, retyping the post as HTML into the Drive call is about a third); the rest is content read into the chat and turns. Competitor pages were only ~10% (30k tokens). The approval page itself costs about 14 cents (the `findings.json` Claude writes in any format).

Trimming done (2026-10-05):
- **Fewer turns** (each turn re-reads the whole chat): tools loaded once up front; independent calls in one turn; scripts chained with `&&` and ending in `cat`. Target about 14 turns for `-analyze` and 8 for `-fix`, from 29 and 27.
- **Competitor digests** instead of full pages (26k instead of 82k characters for the 5 pages); the full text stays on disk and the gap rule is checked with `grep`.
- **Sitemap Cache kept locally** and filtered by `refresh_sitemap.py`: ~2.7k tokens instead of ~25k (the old route read the raw base64 spreadsheet into the chat). Tested: 8 of the 8 links the Opus run chose are in its output. Re-downloaded only when older than 7 days; otherwise zero Drive calls.
- **Short script output:** facts summary 1k characters instead of 22k, link check a few lines, crawl summary without the outline.
- **`refresh_decisions.py`** replaces about five exploratory `-fix` turns and makes the gate deterministic. Checked against the Opus `-fix` run: same 23 applied, 2 skipped, 3 notes.
- **`/write`'s style rules summarized inside `refresh-fix.md`**, so `-fix` no longer reads `write.md` (two reads of ~2.6k tokens each last time).
- **Token report dropped** from both commands; `refresh_cost.py` replaces it.

**First test of the trimmed `-fix`** (2026-10-05, Sonnet 5.5, same 13 saved decisions as the Opus run): 13 turns and $1.07, against 27 turns and $2.63 on Opus 5.5. The same tokens priced at Sonnet rates are $1.65, so the design change alone is about -35% (turns -52%) and the model change another -37%. What is left: about $0.25 is the HTML round trip into Drive.

What the test found, and the fixes (same day):
- **A note was ignored and the summary misreported it.** D2's note said not to use the keyword as is; the draft copied the AFTER text, which starts with the keyword, and the summary said it had been reworded. The model saw the note and still preferred the fix text. Fix: the decisions script prints a NOTES block, states that a note replaces the fix text it contradicts, and `-fix` must say what it will do differently from the fix text before writing, check every note against the draft, and describe what the draft actually does.
- **A figure on a cited page was not on the page.** "Tokopedia cut its LCP from 3.78 s to 1.72 s" cited a web.dev page that says "improved LCP by 55%". WebFetch returns a model's summary, and the summary supplied the seconds. Fix: `refresh_verify.py` fetches the page itself and prints the real text around each term; a figure goes in only if it is FOUND on the page it is attributed to.
- **A renamed heading breaks an in-post jump link** (`#content-in-short`). The Opus run flagged it; the Sonnet run did not. Fix: a rule to list changed anchors under "Couldn't apply / needs a check".
- **A source of a different kind** (a 2021 case study where the fix asked for 2023 or later) replaced the placeholder without saying so. Fix: keep the placeholder, or say that an older source was used.
- **Output over ~30,000 characters** is saved to a file that must then be read in full (a wasted turn). The decisions script now leaves the snapshot out and `-fix` prints it in the next turn, alongside the source checks.

The Drive upload for the Fix Doc is live (2026-10-05): `scripts/gdoc_upload.sh` posts the HTML to an n8n webhook that creates the Google Doc through the Drive API (`docs/n8n-gdoc-upload.md`; the workflow file is `docs/n8n-gdoc-upload.workflow.json`). `-fix` uses it first and falls back to the Drive connector on exit 4 or 5. Tested: n8n's Google Drive node with Create From Text and Convert to Google Document sends the HTML as plain text (the Doc shows raw tags), so the workflow uses a plain HTTP Request to the Drive API instead; that produced a correct Doc.

## Data sources

| Source | Used for | Access |
|---|---|---|
| Notion Content Library | KW check, funnel, cannibalization | Notion MCP |
| DataForSEO SERP | Organic top 3, AI Overview sources, PAA | `DATAFORSEO_WEBHOOK_URL` |
| DataForSEO keyword overview | Search volume (retarget) | `DATAFORSEO_WEBHOOK_URL` |
| Gemini grounded search | AEO set, third-party fact checks | `GEMINI_WEBHOOK_URL` |
| Sitemap Cache (Drive `1dSPlYc_WD3HGp-kQgw6LVPBZksdAtu4LcBGbo6fQB1U`) | Internal link suggestions. Downloaded once into `.refresh-cache/sitemap.json` and refreshed when older than 7 days | Drive MCP, then `refresh_sitemap.py` |
| `product-context/` | Seobility pricing, features, tone, ICP | Local files |
| `skills/golden-entity-map.md` | Entity map | Inline, unchanged |
| `skills/product-plug.md` | Product mentions in new copy | Inline, unchanged |
| Refresh folder (Drive `1CTthW4EQ9qMEMAh1_xbhyB8GVv3InORS`) | Analyze and Fix Docs | Drive MCP |

All external calls go through the n8n webhooks: scripts source `.env` and call the webhook, same as the existing scripts. No API keys in the repo.

### New files (names proposed)

- `.claude/commands/refresh-analyze.md`, `.claude/commands/refresh-fix.md`
- `scripts/refresh_crawl.py`: crawl our post, snapshot, paragraph IDs
- `scripts/refresh_serp.sh`: 3 SERP calls grouped into result sets; organic top 3 + backups, AI Overview sources, PAA
- `scripts/refresh_aeo.sh`: 3 phrasings × 5 grounded Gemini runs, redirect resolution, citation ranking
- `scripts/refresh_fetch.py`: fetch and strip competitor pages; writes the full text and a short digest per page
- `scripts/refresh_sitemap.py`: local copy of the Sitemap Cache (`status`, `ingest`, `query`): all remaining blog posts plus a scored wiki shortlist
- `scripts/refresh_decisions.py`: `-fix` Step 1 in one call: resolves decisions, gate, live-page check, apply list, silent link fixes, snapshot text
- `scripts/refresh_cost.py`: exact tokens and API-equivalent dollars of past runs, from the saved chat transcripts
- `scripts/refresh_links.py`: link status check, redirects, soft 404s, dirty links; modes: a post's snapshot, `--urls`, `--md` (links a draft adds). Short summary on stdout, full results in `links.json`
- `scripts/refresh_checks.py`: mechanical SEO checks on the snapshot (added 2026-10-05 to lift Sonnet's recall): H1 count, title 50–60, meta 120–155, years older than this year, close-variant keyword presence in H1/title/meta/intro/H2–H3 (core words after dropping articles, pronouns, prepositions, auxiliaries and question words; 6-letter stems), stuffing (over 2 per 100 words or 3+ in one block), anchors under 3 words, product links with where they sit, paragraphs over 4 sentences, FAQ questions vs body. Prints a short report and writes `checks.json`. Run in the Step 3 chain; Step 8 reruns it for `--faq` only. Claude still judges what becomes a finding
- `scripts/refresh_facts.sh`: grounded Gemini checks for third-party pricing, features, specs and stats (2 runs per claim)
- `.refresh-cache/` added to `.gitignore`
- `scripts/refresh_to_gdoc.py`: wraps `write_to_gdoc.py` unchanged and adds a light green highlight (`#d9ead3`) for new copy between `<!-- new -->` / `<!-- /new -->` lines (decided 2026-10-01, so `/write`'s script stays untouched)
- `.refresh-cache/[slug]/run.json`: the `-analyze` run state `-fix` needs (keywords, confirmed H1, funnel, tier, entity map, competitor URLs, Analyze Doc link). `-fix` must run on the same machine as `-analyze`.
- ~~Token log~~ (dropped 2026-10-05): the in-command token report used the session usage tool, which only reports approximate context size and plan percent, and cost two extra turns per run. `refresh_cost.py` reads the saved transcripts instead.

---

## Drive connector limits (tested 2026-09-29)

- It creates Docs from HTML only. No tabs, and it can't edit a Doc after creating it. Hence two Docs, and `-fix` creates a new Doc instead of writing into the Analyze Doc.
- No real Google suggestions or comments. Changes are shown through formatting.

---

## Open for build time

- Whether Google AI Mode results are worth adding.
- Token cost per analyze + fix run (tracked with the app's usage tool). If too high, cut the comparison sets to top 2.

## Parked

- `-fix` writes `Funnel` and `Last Updated` back to Notion.
- Retarget mode and its SERP overlap threshold.
- `/score` adopting parts of this design.

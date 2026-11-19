# Refresh Analyze Command

Invoke with: `/refresh-analyze [blog URL] primary kw: … secondary kw: … contextual kw: …`

> **Status: draft, version 1 (optimize mode only).** Design and test notes: `docs/refresh-design.md`.

Compares a published Seobility blog post against what currently ranks on Google and gets cited by AI search, checks its facts and links, and publishes every finding on an **approval page** (a private claude.ai artifact) where the user clicks Yes/No, skips fixes and adds notes. The same user then runs `/refresh-fix [approval page link]` to apply the approved fixes.

Standalone: not part of the Sera → `/brief` → `/write` → `/score` chain.

## Dependencies
- Notion MCP: Content Library lookup (Step 2)
- `scripts/refresh_crawl.py`, `scripts/refresh_links.py`, `scripts/refresh_checks.py`, `scripts/refresh_sitemap.py`: crawl, link check, mechanical SEO checks and sitemap cache status in one call (Step 3)
- `scripts/refresh_serp.sh`: organic set, AI Overview sources, PAA, performance tier (Step 4b)
- `scripts/refresh_aeo.sh`: AI-cited set (Step 4b)
- `scripts/refresh_fetch.py`: fetch competitor pages, write full texts and short digests (Step 5)
- `skills/golden-entity-map.md`: entity map, run inline (Step 7)
- `scripts/refresh_facts.sh`: third-party fact check (Step 8)
- `scripts/refresh_sitemap.py`: internal link candidates from the local Sitemap Cache copy (Step 8)
- `product-context/seobility_pricing.md`, `seobility_features.md`: Seobility claims (Step 8), product link caps and capability (Step 9)
- Google Drive MCP: only to refresh the Sitemap Cache copy when it is missing or older than 7 days (Step 5)
- `templates/refresh-approval.html`: the approval page template (Steps 8 and 10). Never edit it during a run.
- `Artifact` tool (publish) and `ArtifactData` tool (load the findings): approval page (Step 10)
- Afterwards: `python3 scripts/refresh_cost.py` shows the exact tokens and API-equivalent cost of the run.

All external API calls go through the scripts (n8n webhooks). Never call the webhooks directly.

**Content Library (Notion):** `collection://344eba87-0b26-817b-980a-000b96d30f1d`
**Sitemap Cache (Drive):** `1dSPlYc_WD3HGp-kQgw6LVPBZksdAtu4LcBGbo6fQB1U`

---

## Overview

| # | Step | Stop |
|---|---|---|
| 1 | Check the input | |
| 2 | Notion lookup | **STOP 1: keyword check** (only when something is flagged) |
| 3 | Crawl the post, save a snapshot | |
| 4a | Build the 3 AEO phrasings | **STOP 2: H1, primary KW, phrasings** |
| 4b | Searches: SERP + AEO | **STOP 3: competitor lists** |
| 5 | Fetch and strip competitor pages | |
| 6 | Strategy | **STOP 4: H1, funnel** |
| 7 | Golden entity map | |
| 8 | Fact and link check | |
| 9 | Judging: write the findings | |
| 10 | Publish the approval page | |

At each STOP, show the stop's content and wait for the user. Between stops, keep chat updates to one line per step ("Crawled: 68 blocks, 22 links").

**Keep the run cheap.** Every turn re-reads the whole chat, so turns and pasted text are the cost (a full run was $3.30 at 29 turns on Opus 5.5). Rules that hold throughout:
- Load all deferred tools **once, in the first turn** (Step 1). Never load a tool later.
- Put independent calls in the **same turn**, and chain scripts with `&&` in one Bash call. End a Bash call with `cat` of the file you will need next, so it needs no separate Read.
- Read the **digests** of the competitor pages, never the full texts. Check a topic in the full texts with `grep -n -i`, not by reading them.
- Never read a file that a script already summarized (links.json, facts.json, the sitemap sheet). Never re-read this command file.
- No status turns: no token reports, no "checking" calls.

The cache folder for this run is `.refresh-cache/[slug]/`, where `[slug]` is the last part of the URL path. `/refresh-fix` needs it, so `-fix` must run on the same machine.

---

## Step 1: Check the input

Parse flexibly: labels may be missing colons, keywords may be comma-separated.

- **URL:** required, must contain `/blog`. Anything else: stop with "Only Seobility blog posts are supported (the URL must contain /blog)."
- **Primary KW:** required. If missing, ask for it.
- **Secondary KW, Contextual KW:** optional. Contextual KWs left empty are filled from the entity map in Step 7.
- **Head-term warning:** a primary keyword under 3 words gets: "'[kw]' is a head term. Competitor sets for head terms are broad and often off-topic. Continue, or use a longer keyword?" The user can continue.

**Load the tools in this first turn**, as two parallel ToolSearch calls: `select:ArtifactData,WebFetch`, and a keyword search for `notion-search notion-fetch download_file_content` (max_results 6). The Drive download tool is only used if Step 5 finds the sitemap copy missing or stale; loading it now saves a whole turn later.

## Step 2: Notion lookup (STOP 1)

1. Search the Content Library by URL slug: `notion-search(query="[slug]", data_source_url="collection://344eba87-0b26-817b-980a-000b96d30f1d")`, and in the same turn search for the primary keyword (step 3). Fetch all plausible results in one parallel turn and match on the `URL` field **by slug**, so `https`, `www` and trailing-slash differences don't matter.
2. From the matched row, read `Primary KW` and `Funnel`. Ignore `Not Evergreen`.
3. **Cannibalization:** search the database for the user's primary keyword. Fetch plausible results and list every other row whose `Primary KW` matches it (case-insensitive, ignoring punctuation). Exclude this post's own row.
4. If the post isn't in the library, say so and continue. The funnel is then classified by Claude at Stop 4.

**No flags → no stop.** If the keywords match, no cannibalization was found, the post is in the library and there's no head-term warning, say so in one line ("Notion: keyword matches, funnel Top, no cannibalization.") and continue to Step 3 without waiting.

**Otherwise, STOP 1** shows:
- Notion `Primary KW` next to the user's primary keyword, marked "match" or "differs"
- Notion `Funnel` (or "not in library" / "empty")
- Cannibalization: other posts targeting the same primary keyword (title + URL), or "none found"
- The head-term warning, if any

**If the keywords differ:** ask whether the new keyword is a change of target or just a different wording of the same one.
- Change of target → stop: "Changing the primary keyword is retarget mode, which isn't built yet. Run again with the Notion keyword ([kw]) to optimize the post as it is."
- Same target (Notion is outdated or worded differently) → continue in optimize mode with the user's keyword.

When STOP 1 is shown, wait for the user to continue.

## Step 3: Crawl, link check, sitemap status

One Bash call (the `&&` chain stops at the first failure):
```bash
python3 scripts/refresh_crawl.py "[URL]" && python3 scripts/refresh_links.py [slug] && python3 scripts/refresh_checks.py [slug] --kw "[primary kw]" && python3 scripts/refresh_sitemap.py status && cat .refresh-cache/[slug]/snapshot.md
```
The output has five parts: the crawl summary, the link check (counts plus only the links that need attention, see Step 8), the mechanical SEO checks (see Step 9), the sitemap cache status, and the snapshot text: H1, title tag, meta description, dates, every block with its ID (P1, P2, …) and the link list. Findings refer to these block IDs. If the crawl returns `data_available: false`, stop and show the error. Remember the link check, the SEO checks and the sitemap status for later; don't run them again (Step 8 reruns the checks only for the FAQ part).

## Step 4a: Build the AEO phrasings (STOP 2)

Build the 3 AEO phrasings from the primary keyword:
1. **As typed:** the primary keyword exactly, lowercase, no punctuation.
2. **Plain question:** the question a person would type into an AI assistant, keeping the keyword's words. If the keyword is already a question, ask the same thing in different words, so phrasings 1 and 2 aren't the same search.
3. **Conversational:** 1–2 sentences, first person: the reader's problem, then the question.
   - Problem source: the "Core Issue" line of the post's "In this post" box if there is one, otherwise the intro paragraphs before the first H2.
   - No persona ("I'm an SEO manager"), no brand names, nothing from the post's answer, under 40 words.
   - If the intro has no clear problem, use a second plain question worded differently from phrasing 2.

**STOP 2** shows exactly this, then waits:

> **H1:** [the post's current H1]
> **Primary KW:** [primary kw]
> **AEO phrasings:**
> 1. [phrasing 1]
> 2. [phrasing 2]
> 3. [phrasing 3]
>
> Reply **confirm**, or edit the phrasings. The searches take about 40 seconds.

## Step 4b: Searches (STOP 3)

Before starting, say in one line that the searches take about 40 seconds. **Run both scripts in parallel** (two separate Bash calls in the same turn), with the confirmed phrasings:
```bash
./scripts/refresh_serp.sh "[primary kw]" "[URL]"
./scripts/refresh_aeo.sh "[URL]" "[phrasing 1]" "[phrasing 2]" "[phrasing 3]"
```

**Check the lists before showing them.** The scripts skip by URL only. Look at every top 3 entry's title and URL: a page that isn't an article (tool page, dashboard, product or pricing page, login, PDF, video) is swapped for the next backup from the same set. Say which ones you swapped and why.

**STOP 3** shows:
- **Organic top 3:** title + URL, with up to 3 backups.
  - `recommendation_basis: "snapshot"` and more than one set: show the recommended set as the top 3, then one line: "Google returned [n] other result sets; the recommended one matches Google's stored results."
  - `"no_snapshot"`: if the sets split, recommend the set whose pages actually answer the keyword and say why.
  - `"no_match"`: "None of the live result sets matched Google's stored results, even after a retry." Show each set's top 3 and ask the user to pick one or check the keyword.
- **AI Overview sources**, if the confirmed set has an AI Overview (title + URL).
- **AI-cited top 3:** URL + how many of the 3 phrasings and 15 runs cited it, with up to 3 backups.

The user can swap competitors. Wait for the user to confirm.

**Never show** our post's rank, position or tier, in chat or on the approval page, and never mention that a tier exists (no "tier checked" status lines). Keep the confirmed set's `tier` (`protect` / `striking_distance` / `needs_content`) for Step 6 and Step 9.

## Step 5: Fetch and strip competitors

After STOP 3 is confirmed, one turn with up to two parallel calls.

**(a) Bash:** fetch the confirmed organic top 3 and AI-cited top 3 (a page in both sets is fetched once), then print the digests and the entity map skill:
```bash
python3 scripts/refresh_fetch.py --slug [slug] [url1] [url2] … && cat .refresh-cache/[slug]/competitors/*.digest.md skills/golden-entity-map.md
```
Each digest (about 2k tokens) has the outline with a lead sentence per section, formats, FAQ questions and the sentences with numbers. **Use the digests for the gap rule, the format table and the funnel check.** The full text of each page is in `competitors/N_domain.md`: before you call something a gap, `grep -n -i "term" .refresh-cache/[slug]/competitors/*.md` to confirm the page really doesn't cover it. Don't Read whole files. If a page fails, fetch the next backup from the same set in the next Bash call and say so in one line.

**(b) Drive, only if Step 3 said the sitemap cache is MISSING or STALE:** call the Drive connector's `download_file_content` for the Sitemap Cache (file ID above). The result is too large to show, so the tool saves it to a file and prints the path. Don't open that file; Step 8 passes it to the script.

## Step 6: Strategy (STOP 4)

**Protect tier (rank 1–3):** skip the H1 suggestions and the funnel switch. Show the tables below with "Keep as is" for the H1 and funnel, note any funnel mismatch for information only, and continue after the user confirms.

**Otherwise, STOP 4** shows three things, with no commentary beyond what's listed:
- **Meta titles:** table `Page · Meta title`, ours first, then each competitor. Replace any `|` in a title with `–` so the table doesn't need escapes. No H1 column. Then the H1 options: "Keep as is: [current H1]" or 2–3 suggested H1s, each with a one-line reason, and your pick. Suggested H1s contain the primary keyword, follow the post's heading case (see Step 9) and are **60 characters or fewer** (count them; show the count after each, e.g. "(52)"). Rework any option that's longer rather than listing it. Don't explain what's wrong with the current H1; the reasons on the suggestions are enough.
- **Funnel:** table `Page · Funnel`: ours (Notion; if empty, `N/A` or not in the library, classify it from the post) and each competitor's, classified from its page. Funnel stages: Top, Middle, Bottom. Then one line: "No mismatch: keeping [stage]." or the mismatch question below. Don't mention product link caps or how many product links the post has.
- **Format:** table `Page · Format · Words · Tables · FAQs · Notes`, ours first. Notes is short (e.g. "Key Takeaways block", "7 schema FAQs"). Then at most one line on the pattern (e.g. "AI-cited pages are statistics roundups with tables").

End with what to reply: "**H1:** 1, 2, 3, keep as is, or your own wording · **Funnel:** keep or change".

**Funnel mismatch** (most competitors sit at a different stage): the user decides.
- **Change:** gaps specific to the new stage (tool comparisons, "how to choose") become findings. Show the **section map** below and get it approved before Step 7.
- **Stay:** those stage-specific gaps are excluded. List what was excluded and why as a For info note.

**Section map** (only after a funnel switch). Columns `H level · Current section · Decision · Why`. Rows follow the **current** order. New sections are inserted where they would go, H level shows e.g. `H2 (new)` and the heading copy is in *italics*. Moved sections say where to ("Move → after [section]"). Decisions: keep, rewrite, merge, cut, move, new. Findings in Step 9 build on the approved map; findings for cut sections are dropped.

Everything after this stop uses the confirmed H1 and funnel. **Product link caps** (internal, not shown at the stop) use the chosen funnel: Top 1, Middle 2, Bottom 2 body product links, not counting a dedicated Seobility section or the closing CTA.

## Step 7: Golden entity map

Run `skills/golden-entity-map.md` inline, unchanged (its text was printed in Step 5; don't read it again), with:
- Target topic: the confirmed H1. Brand: Seobility.
- Optional inputs: our snapshot and the competitor digests. These are the research. **Don't run new web searches** for the entity map: the competitor pages already show the current landscape.

Entity rule (from `/brief` 1c): the SERP format decides what counts as an entity. In listicles and comparisons, tool names count. In other formats, only concepts, methods, standards and technical terms.

Keep the JSON internally (it's never shown raw). If the user gave no contextual keywords, use the top-weighted `must_include` entities as contextual keywords.

## Step 8: Fact and link check, internal link candidates

Always runs. **One Bash call** does the claims file, the fact check, the sitemap, the page template and the product-context lookups. You already have the link check from Step 3.

```bash
cat > .refresh-cache/[slug]/claims.json <<'EOF'
[{"id": "C1", "block": "P38", "kind": "pricing | feature | spec | stat | reference | definition", "entity": "Tool or source", "claim": "the claim as written"}]
EOF
./scripts/refresh_facts.sh "[URL]" .refresh-cache/[slug]/claims.json
python3 scripts/refresh_checks.py [slug] --kw "[primary kw]" --faq "[the FAQ questions you plan to keep, replace or add]" | sed -n '/^FAQ vs body/,$p'
python3 scripts/refresh_sitemap.py ingest "[saved file path from Step 5]"   # only if you downloaded it
python3 scripts/refresh_sitemap.py query [slug] --terms "[entity names, plus topics the competitors cover that our post lacks]"
sed 's/{{TITLE}}/[confirmed H1 without trailing punctuation] approvals/' templates/refresh-approval.html > .refresh-cache/[slug]/approval.html
grep -n -i -B1 -A3 "[the specific plan, price, trial or feature terms the post mentions]" product-context/seobility_pricing.md product-context/seobility_features.md
```

1. **Links** (from Step 3):
   - `dead` and `soft_404` → required Applied fix (replace or remove the link).
   - `moved` redirects → Applied fix (update to the final URL, or replace if the target changed topic). `minor` redirects → no finding (`-fix` quietly updates them).
   - `unverified` → never a dead-link finding. One For info note: "[n] links on [domain] couldn't be checked (the site blocks bots)."
   - Dirty links: `affiliate` → finding. `possible_affiliate` → finding only if the parameter is clearly an affiliate code. `tracking` → Applied fix (clean URL). `ai_tracking` → no finding (`-fix` strips it silently).
2. **Third-party claims:** pull every checkable third-party claim from the snapshot into `claims.json`. Go through the snapshot block by block and take **every sentence that states a fact about something outside Seobility**; don't stop at the first handful (a run that extracted 6 claims missed a wrong definition). Always include:
   - **Definitions** (`kind: "definition"`): every sentence that says what a metric, tool, standard or term measures, is or does (e.g. "INP measures a user's first interaction", "TTFB is the time until the first byte arrives", what a Google update targets). These are the most likely to be wrong or out of date. Include the number or threshold the post attaches to it.
   - **Thresholds and benchmarks** (`spec`): "good" and "poor" cut-offs, limits, sizes, timings.
   - Other tools' pricing and features, stats, studies, and references to Google updates, tools or metrics that may be outdated.
   Keep one claim per entry, quoted as written, and aim for every distinct metric or tool the post defines, not a sample. The script prints the claims that need attention (with what current sources say, a correction and sources) and one line for the confirmed ones.
   - `outdated` / `wrong` → finding, using the printed `now` and `fix`. Check the sources: if none is the vendor's own page or the original study, make the fix a `[TODO · VERIFY: …]` instead of a correction.
   - `disputed` / `unverifiable` → finding with a `[TODO · VERIFY: …]` fix, never a guessed correction.
3. **Seobility claims:** check every Seobility pricing, plan, limit, trial and feature claim against the printed product-context lines. Wrong ones → required Applied fix. Anything the lines don't confirm → `[TODO · VERIFY: …]`. If the grep is too narrow to decide, read the relevant section once.
4. **Pricing rules** (both Seobility and third-party): expand inherited tiers ("Everything in Starter, plus X" = Starter's full list + X), never mix monthly and annual prices, match currencies.
5. **Dated claims:** stats and studies older than 3 years (from today's date), and outdated references (deprecated tools or metrics, old Google updates described as new) → findings.
6. **Outdated years** in the H1, title tag or meta description (e.g. "SEO Trends 2023") → finding.

## Step 9: Judging

Claude does all judging. Each finding gets a **fix type**, a **bucket** (Decide, Applied or For info, see "Buckets" below), an internal **priority** (High / Medium / Low, used for sorting and the tier, never shown), a **Where** and a **Suggested fix**.

### Fix types (also the order `-fix` applies them)
1. **Add or restructure:** new sections, FAQ refresh, prose → table or steps, reordering sections.
2. **Edit in place:** keyword placement, title and meta, heading rewording, direct answers, naming or explaining entities.
3. **Replace or verify:** outdated stats, dead links, pricing and features.

### Gap rule
A topic is a gap when 2 of 3 pages in a set cover it and our post doesn't.
- Organic set → SEO gap. AI-cited set → AEO gap.
- A gap in both sets is listed once, in the SEO table, marked "also AEO".
- A missing entity that's also a competitor gap is one finding, in the Entities table, with the overlap in the Problem text ("Missing. Also covered by 2 of 3 top results.").

### What gets checked
| Area | Checks |
|---|---|
| **SEO** | Topic gaps (organic set); format gaps (tables, steps); exactly one H1, containing the primary keyword; title tag 50–60 characters with the keyword near the front; meta description 120–155 characters; keyword in intro and headings; keyword stuffing (flag existing ones); anchors under 3 words; product link caps; missing internal links (from the Sitemap Cache); section order vs competitors (2 of 3 pattern). **The first eight are measured by `refresh_checks.py` (see below)** |
| **AEO** | Topic gaps (AI-cited set); clear definition near the top; vague headings; no direct answer under a question heading; sections that don't stand alone (vague "this"/"it"); key takeaways block; enumerable content written as prose (→ list); answer the H1 early (sections that answer the H1 first, background later, closing section, FAQs last) |
| **Entities** | Missing and thin `must_include` entities; `must_avoid` entities found in the post (status Missing / Thin / Avoid goes in the item's `why`) |
| **Fact & link** | Moved redirects, dirty links, unverified links, outdated claims and references, outdated years in H1/title/meta, third-party pricing and features (Seobility errors and dead links are required fixes) |

**Heading case matches the post:** look at the post's existing H2s and H3s (and the H1). If most are sentence case ("Why website speed is so important"), write every suggested, new or renamed heading (in H1 options, BEFORE → AFTER fixes and new section titles) in sentence case, the FAQ heading and questions included. If most are title case, use title case. Never change the case of headings no finding touches.

**Mechanical SEO checks (`refresh_checks.py`, printed in Step 3).** Don't re-measure these by eye; turn every `← FLAG` and every miss into a finding, and don't invent findings for a check that passed:
- **H1 count, title length, meta length:** a `← FLAG` is a finding (Decide: title tag and meta changes). Title near the front: flag when the first keyword word starts after about char 25.
- **Outdated years:** a finding (see Step 8, item 6).
- **Keyword placement:** H1, title, meta and intro each report `full`, `partial` or `none` using the close-variant rule below. `partial` or `none` is a finding for that place, and the output lists the missing core words. "Headings with the keyword" is information: suggest at most one heading rewording when none has it, and never push the keyword into every heading.
- **Keyword stuffing:** a flagged density or a block with 3+ occurrences is a finding only if the block reads as stuffing (a list of updates naming "Google core update" in each item is not). Check by reading that block.
- **Anchors under 3 words:** every listed anchor is a finding, as one grouped Applied item per section (one `A` item with each anchor and its better 3+ word anchor in the details).
- **Product links:** compare the body count with the cap for the confirmed funnel (Top 1, Middle 2, Bottom 2). Over the cap is a Decide item (which links to cut or merge); a register or trial link and a link in the closing section don't count.
- **Paragraphs over 4 sentences:** no finding; `-fix` splits them silently.
- **FAQ vs body:** the Step 8 call checks each question you plan to keep or add. `LIKELY ANSWERED` or `POSSIBLY ANSWERED` fails the fit gate (not already answered in the body) unless you read the block and it only mentions the topic. `partial overlap` and "too short to judge" need your reading. An existing FAQ question that the body already answers is a Replace or Cut candidate.

**What "contains the primary keyword" means** (H1, title tag, meta description, intro, headings): the keyword or a close variant. Close variants count as containing it: articles, pronouns and determiners swapped ("a website" / "your website" / "the website"), singular vs plural, word order changes that keep the meaning, and added words in between. Only flag a placement when the keyword's core words are missing (e.g. "load" is missing from "how fast does your website need to be"). For the intro, the "In this post" box counts: its heading and lines are part of the intro. Sentence case vs title case in existing headings is editorial and never a finding.

**Internal links:** the candidates are in the Step 8 sitemap query: every remaining blog post (the score is only keyword overlap, so judge by meaning) plus a wiki shortlist. The post itself and pages it already links are excluded. Suggest only content pages that fit a specific passage. Each suggestion names the block and the anchor (3+ words). Never read the Sitemap Cache sheet yourself.

### Entities
Each `must_include` entity is:
- **Covered:** named and explained. No finding.
- **Thin:** named but unexplained → edit in place: explain it in plain words and tie it to what the reader does.
- **Missing:** placed with the smallest change that covers it:
  1. Name it in an existing sentence (the post discusses the concept without naming it) → edit in place
  2. Add a paragraph or bullet (an existing section is the natural home) → edit in place
  3. New H3 under an existing H2 → add/restructure
  4. New H2 (a distinct concept with no home in the post) → add/restructure

Each entity is placed in exactly one section, where it's most central; broad entities go under the first H2 where they fit. The entity's `context` is the fix direction, never copied verbatim. Priority from `semantic_weight`: 9–10 High, 6–8 Medium. Don't force entity names into headings, and don't use entities to pick internal links.

### Info gain (Decide; at least one Yes, except in the protect tier)
Propose each `novel_information_gain` angle as a finding. Placement uses the angle's `context` and our outline, with the `/brief` 1d rule: H2 if it's a distinct concept the reader needs on its own, H3 if it deepens an existing H2. Where says exactly where ("new H2 after Rendering Problems", "expand P14").

### FAQ refresh (every run)
One Decide item per question (bucket `faq`), with its `action` (Keep (rewrite), Replace, Cut, Add) and `source`.
- **Sources, in order:** (1) fit gate: the question is about this post's topic and not already answered in the body, or in a section this run proposes (if an approved Decide item would answer it, drop the question or name the dependency in its `why`); (2) People Also Ask from the confirmed SERP set (fallback: related searches, then the post's own content); (3) our own angle: questions from the info gain angles or entities. Competitor FAQs are not a source, only a duplication check: if our block would mostly repeat a competitor's, flag it and prefer questions they don't answer. Questions from AI-cited pages aren't used.
- **Actions:** Keep (rewrite): fits and has PAA demand, or comes from our own angle; at minimum the answer is paraphrased. Replace: fails the fit gate or has no demand, and a stronger question exists. Cut: fails the fit gate and nothing better exists, or the block is over 6. Add: a PAA or own-angle question the post doesn't cover, up to 6.
- Writing quality never decides whether a question stays.
- No FAQ block → propose a new one from the same sources. Size 3–6. Placement: the last section, after the closing section, headed "FAQs About [Primary KW]" (in the post's heading case, reworded so it reads naturally). A block elsewhere moves there.
- Answers: 40–60 words, direct answer first, specific facts, entities named only where natural, no repeating the body.

### Buckets
Only real judgment calls need a click. Every finding goes in exactly one bucket:
- **Decide** (Yes or No on each; `-fix` won't run until all are answered):
  - `info_gain`: each info gain angle. At least one Yes, except in the protect tier.
  - `faq`: each FAQ question with its action.
  - `decide`: anything that adds, cuts, merges or moves a section; adds a table or turns prose into a list or steps; changes the H1, title tag or meta description; renames a heading.
- **Applied** (`applied`; applied unless the user skips it): edits in place that don't change structure. Keyword placement in the intro, direct answers, entities named or explained (ladder levels 1–2), internal links, anchors, typos, moved redirects, factual corrections from a primary source, `[TODO · VERIFY]` placeholders. **Required** (`required: true`, no Skip button): dead links and soft 404s, wrong Seobility pricing or features, and in the protect tier the full fact check.
- **For info** (`notes`, no decision): unverified links, confirmations ("all 18 links work"), excluded gaps when the funnel was kept, the count of verify placeholders.

**Section packages:** when several findings touch the same section and at least one of them is Decide-level, merge them into one Decide item for that section (e.g. "P14: rename the H2, open with a direct answer, define page load time, add a thresholds table"). Small Applied fixes elsewhere stay separate. The Details text lists every part, so the user can approve with a note like "Y, but no table".

### Performance tier (internal, never mentioned)
From the confirmed SERP set's `tier`. "Up one level" means Low → Medium → High; High stays High. Required fixes and the Decide bucket are never affected.
- **`striking_distance` (rank 4–10):** on-page findings go up one level: title, meta, keyword in intro and headings, heading rewording, one or two missing sections.
- **`needs_content` (11+ or not found):** content gaps, missing entities and info gain go up one level.
- **`protect` (rank 1–3), maintenance mode:**
  - **Required** = dead links and the full fact check: Seobility claims plus third-party pricing, features, studies and stats. The FAQ refresh still runs as Decide items.
  - **Info gain is optional:** set `meta.info_gain_required: false`. A paragraph or an H3 only, never a new H2.
  - **Don't make** findings that change structure (new H2s, cuts, merges, reordering), keyword positioning, the H1, the title tag or the meta description. Exception: an outdated year in the H1, title or meta is still flagged.
  - **Allowed minor findings:** a missing entity at ladder level 1–2, a thin entity explained, a direct answer under a question heading, a missing internal link.

## Step 10: Publish the approval page

Four turns. The page file was made in Step 8.

1. **Publish it** with the `Artifact` tool: `file_path` = the absolute path of `.refresh-cache/[slug]/approval.html`, `icon` = `checklist`, `description` = "Approve or skip the /refresh findings for [H1] before running /refresh-fix.", `capabilities` = `{"db": {"rules": [{"path": "", "read": "view", "write": "admin"}]}}` (only the owner and editors can save decisions). Keep the returned URL.
2. **One Bash call** writes both files, then counts the items:
   - `.refresh-cache/[slug]/findings.json`, with `meta.approval_url` set to the URL from step 1. This file is the whole report: the page renders it and `-fix` works from it. Shape:
     ```json
     {
       "meta": {"h1": "confirmed H1", "url": "…", "slug": "…", "primary_kw": "…", "secondary_kws": [], "contextual_kws": [],
                "mode": "Optimize", "funnel": "Top (kept)", "date": "YYYY-MM-DD", "info_gain_required": true,
                "approval_url": "…"},
       "top_performers": [{"set": "Organic | AI-cited", "page": "Site: title", "url": "…"}],
       "notes": ["For info lines, one string each"],
       "items": [{
         "id": "I1 | Q1 | D1 | A1",
         "bucket": "info_gain | faq | decide | applied",
         "section": "where in the post, e.g. Metrics (P30) or New H3 under P14",
         "title": "what changes, one line; BEFORE → AFTER for headings, title tag and meta description",
         "why": "a few words (Decide items only)",
         "action": "Keep (rewrite) | Replace | Cut | Add (FAQ only)", "source": "PAA | Related search | Own angle (I1) (FAQ only)",
         "required": false, "important": false, "priority": "High | Medium | Low",
         "checklist": ["new_sections | removed_merged | restructured | faq | key_takeaways | entities | outdated_info | links | h1 | meta"],
         "details": {"problem": "full problem text", "fix": "full fix text: placement, what to cover, exact AFTER wording, [TODO · VERIFY: …]"}
       }]
     }
     ```
     - **IDs:** `I1…` info gain, `Q1…` FAQ, `D1…` other Decide items, `A1…` Applied. Order: Decide items by priority; Applied items in post order (their `section` groups them on the page, so use the same `section` text for fixes in the same part of the post).
     - `important: true` bolds a title. Use it for wrong facts.
     - `checklist` tags tell `-fix` which change-checklist lines to tick when the item is applied.
     - Never show the rank, position or tier anywhere in the file.
   - `.refresh-cache/[slug]/run.json`: URL, slug, keywords (primary, secondary, contextual), confirmed H1, funnel, mode, tier, the approval page URL, the entity map JSON, the confirmed competitor URLs, today's date.
   - End the call with `jq '.items | length' .refresh-cache/[slug]/findings.json`.
3. **Load the findings:** `ArtifactData` `set` with `url` = the page, `collection` = `run`, `doc_id` = `findings`, `file_path` = the absolute path of `findings.json`. Never retype the findings inline. The page fills in as soon as the data arrives. The result says the document was committed; that is the check, don't read it back.
4. **Reply in chat** with: the approval page link, the counts (Decide items by type, Applied, required, For info), the number of `[TODO · VERIFY]` items, and one line: "Decide on the page, then run `/refresh-fix [page link]`." Add: "Exact cost of this run: `python3 scripts/refresh_cost.py`." Don't paste the findings in chat.

**Fallback:** if publishing or loading the findings fails, say so and give the findings inline in chat as compact tables (Decide, Applied, For info) so nothing is lost. `findings.json` stays in the cache either way.

---

## Rules
- Version 1 is optimize mode only. A changed primary keyword stops at Stop 1.
- URLs must contain `/blog`. Primary keyword is required.
- Stop at each stop and wait for the user. STOP 1 is skipped when nothing is flagged.
- Never show our post's rank, position or tier anywhere.
- All searches use the primary keyword, US Google, English. Never the H1.
- Claude judges; Gemini only searches (AEO set, third-party facts). Scripts do the mechanical work.
- Never call the n8n webhooks directly; use the scripts.
- Cost rules: tools loaded once up front, independent calls in one turn, digests instead of full competitor pages, no files read that a script already summarized, no token report.
- `unverified` links are never reported as dead.
- Anything that can't be confirmed from a live primary source becomes `[TODO · VERIFY: …]`, never a guessed correction.
- Out of scope: editorial changes to existing copy (em dashes, UK vs US spelling, tone), technical SEO (schema, alt text, page speed), URL slug changes, scoring.
- No `|` in any table cell. Funnel stages are Top / Middle / Bottom.
- The approval page is the only output. Nothing is written to Drive by `-analyze`. Cache files stay in `.refresh-cache/` (git-ignored).

# Refresh Fix Command

Invoke with: `/refresh-fix [approval page link]`

> **Status: draft, version 1 (optimize mode only).** Design and test notes: `docs/refresh-design.md`.

Applies the fixes approved on the approval page (from `/refresh-analyze`) to the crawled copy of the post, and creates a Fix Doc (`Fix_[H1]`) in Drive with an approval summary, a change checklist and the clean edited copy.

Needs the cache from the `-analyze` run (`.refresh-cache/[slug]/`), so it runs on the same machine.

## Dependencies
- `ArtifactData` tool: read the findings and decisions from the approval page (Step 1)
- `scripts/refresh_decisions.py`: resolves the decisions, checks the gate, checks the live page, prints the apply list (Step 1)
- `product-context/Seobility_tone_of_voice.md`: voice for new copy (Step 1). `skills/product-plug.md` and `seobility_features.md` only when an applied item needs a Seobility product mention (Step 3)
- `scripts/refresh_verify.py`: checks figures against the real text of a source page (Step 2). `WebFetch` only to find a source, never as evidence
- `scripts/refresh_links.py --md`: checks the links the draft adds (Step 4)
- `scripts/refresh_to_gdoc.py`: markdown → Google-Docs-ready HTML (Step 4)
- `scripts/gdoc_upload.sh`: creates the Fix Doc from the HTML through an n8n webhook, so you never read or retype the HTML (Step 4).
- Google Drive MCP `create_file`: the fallback when the upload script isn't configured or fails (Step 4)
- Afterwards: `python3 scripts/refresh_cost.py` shows the exact tokens and API-equivalent cost of the run.

**Refresh folder (Drive):** the folder ID is `REFRESH_FOLDER_ID` in `.env` (each user sets their own). If it is empty, the Fix Doc is created in My Drive.

---

## Overview

| # | Step | Stop |
|---|---|---|
| 1 | Read the decisions: all Decide items answered? Info gain? FAQ at 3–6? Has the live page changed? | **Stops if the gate fails; asks if the page changed** |
| 2 | Print the snapshot; verify figures against their source pages | |
| 3 | Write the edited post; check every note against it | |
| 4 | Check links, convert, upload `Fix_[H1]` to Drive | |

**Keep the run cheap.** Every turn re-reads the whole chat, so turns and pasted text are the cost (a full run was $2.63 at 27 turns on Opus 5.5). Rules that hold throughout:
- Load the deferred tools **once, in the first turn**, and never later.
- Put independent calls in the **same turn**; chain scripts with `&&` in one Bash call.
- Never re-read this command file or `/write`'s rules: what you need is below.
- No status turns: no token reports, no "checking" calls.

---

## Step 1: Read the decisions

Three turns:

1. **Load the tools:** two parallel ToolSearch calls: `select:ArtifactData,WebFetch`, and a keyword search for `create_file` (max_results 4).
2. **Fetch the run:** two parallel `ArtifactData` calls with the page link as `url` and the **same** `out_dir` (a folder in the scratchpad): `get` with `collection` = `run`, `doc_id` = `findings`; and `list` with `collection` = `decisions`, `query` = `{"limit": 1000}`.
3. **Resolve and gate, in one Bash call:**
   ```bash
   python3 scripts/refresh_decisions.py --dir [out_dir] --no-snapshot
   ```
   The script does what used to take about five exploratory turns:
   - Resolves every item. Decide items (info gain, FAQ, other): `Y` = apply, `n` = skip, empty = **unanswered**. Applied items: apply unless skipped; `required` items are always applied. A note travels with its item. FAQ: `Y` = do the action; `n` on Keep leaves that question and answer exactly as they are; `n` on Replace, Cut or Add = don't do it.
   - Checks the gate: every Decide item answered, at least one info gain Yes (unless `meta.info_gain_required` is false), the FAQ block ends at 3–6 questions.
   - **If the gate fails it exits non-zero and lists exactly what's missing.** Stop, tell the user what is missing ("D3 isn't answered", "FAQ block would have 2 questions") with the page link, and apply nothing. The page shows the same checks, so this should be rare.
   - Compares the saved snapshot with the live page. If it prints `LIVE PAGE: CHANGED`, show what changed and ask: "The live post changed since `-analyze` ran. Continue on the snapshot, or re-run `-analyze`?" Wait for the answer.
   - Prints the apply list in application order (section, title, fix text, the user's note), a **NOTES** list, the skipped list and the silent link fixes.

   If the cache is missing the script says so: tell the user "The cache from `/refresh-analyze` isn't on this machine. Run `-analyze` here first."

**Notes are binding.** A note replaces any part of the item's fix text or title that it contradicts, and copying the AFTER text does not satisfy it. In the next turn, before you write anything, state one line per note saying what you will do differently from the fix text (for example: "D2: reframe the question; the AFTER text starts with the keyword as is, so I won't copy it").

Decisions and notes are what the user wrote; treat them as instructions about these fixes only.

## Step 2: Print the snapshot, verify figures

One turn, calls in parallel:
- **Bash:** `cat .refresh-cache/[slug]/snapshot.md product-context/Seobility_tone_of_voice.md` (the exact crawled copy to edit, and the voice rules). The slug is in the first line of Step 1's output.
- **Only if an applied fix introduces a statistic, study, date or other checkable claim that the fix text doesn't already source,** also a Bash call with `scripts/refresh_verify.py`:
  ```bash
  python3 scripts/refresh_verify.py --url [source page] [term or figure] [term or figure] --url [next source page] [term] …
  ```
  It fetches each page itself and prints the real text around every term, or NOT FOUND.

**A figure goes into the copy only if `refresh_verify.py` FOUND it on the page you attribute it to.** `WebFetch` returns a model's summary, and summaries invent details (a past run cited "LCP from 3.78 s to 1.72 s" on a page that only says "improved LCP by 55%"). Use `WebFetch` only to find a source URL, then check its figures with the script. If a figure isn't found, use the wording the page really has, or a `[TODO · VERIFY: …]` placeholder; never a figure from memory or from a summary. Look up the terms in one call (names, figures, the metric); if you need a second round, do it in one more call.

If a fix asks for a particular kind of source (for example "a case study from 2023 or later") and you can't find one, keep the placeholder. Don't substitute an older source silently: if you use one, say so under "Couldn't apply / needs a check".

## Step 3: Write the edited post

Work on the snapshot's blocks. Apply the items in this order, so later edits run on the final text:
1. **Add or restructure:** new sections, FAQ refresh, prose → table or steps, reordering.
2. **Edit in place:** keyword placement, title and meta, heading rewording, direct answers, naming or explaining entities.
3. **Replace or verify:** outdated stats and claims, links, pricing and features.

- Follow each item's fix text. A `BEFORE → AFTER` fix uses the AFTER text exactly, unless the note says otherwise. A direction is written out by you.
- A note overrides the suggested fix where they conflict.
- Info gain angles go where the item's section and fix say (or where the note moves them).
- **Writing new sections:** use the entity map in `run.json` (read it only if a new section needs entities) for that section and their `context` lines as direction.
- **Keyword placement:** don't push the primary keyword past natural use. If a placement would read as stuffing, skip it and say so in the chat summary.
- **Links:** moved redirects get the final URL. `[TODO · VERIFY]` fixes stay as placeholders.
- **Renamed headings:** if the post links to a renamed heading's old anchor (a link with `#content-…` in the snapshot, such as the jump link in the "In this post" box), the anchor will change when the post is published. Leave the link as it is and list it under "Couldn't apply / needs a check" with the old and the likely new anchor.
- **FAQ block:** apply the approved actions, rewrite every kept question's answer (at minimum a paraphrase), and put the block last, after the closing section, headed "FAQs About [Primary KW]" (or "FAQs about [primary KW]" in a sentence-case post; reword it so it reads naturally, e.g. "FAQs about how fast a website should load"). Answers 40–60 words, direct answer first, specific facts, entities named only where natural, no repeating the body.

**Rules for new copy** (new sections, rewritten FAQs, rewritten sentences):
- The tone file printed in Step 2, plus: address the reader as "you", beginner-friendly, short sentences, active voice, American English. No em dashes, no emojis. No exaggerated claims. No AI filler ("delve", "dive in", "unlock", "leverage", "game-changer", "robust", "seamless", "comprehensive" or "holistic" as filler, "it's important to note", "overall", "to sum up") and no AI patterns ("It's not just X, it's Y", "Whether you're a beginner or a pro", rhetorical-question openers, reflexive groups of three, a one-line summary ending every section, announcer transitions like "This is where Seobility comes in", staccato fragment stacking). Within a section, one word starts at most two sentences. Paragraphs of 2–4 sentences.
- Every link anchor is at least 3 words. Explicit dates, never "recently" or "this year".
- Entities: explain an entity in plain words the first time it appears, inside a sentence about what the reader does with it or what it causes (not a standalone definition). Branded or named entities (Google Search Console, Core Web Vitals, Lighthouse) use their exact name. Never force a keyword into a sentence; never bold keywords.
- **Heading case matches the post:** look at the post's existing H2s and H3s (and the H1). If most are sentence case ("Why website speed is so important"), write every new or renamed heading in sentence case, the FAQ heading and questions included. If most are title case, use title case. Never change the case of headings no finding touches.
- Outside listicles and comparisons, don't name Seobility competitors, never disparage one, never link to a competitor's domain.
- Every Seobility product mention goes through `skills/product-plug.md` (read it, with `seobility_features.md`, only when an applied item needs a product mention), with product link caps from the run's funnel (Top 1, Middle 2, Bottom 2 body product links, not counting a dedicated Seobility section or the closing CTA).
- `must_avoid` entities never appear in new copy.
- Placeholders: `[TODO · TYPE: message]` with TYPE = VERIFY, TEAM or SCREENSHOT.
- Parser rules, only in definitions, FAQ answers and product sentences: name the subject; numbers and proper nouns over adjectives; one claim per sentence. In Seobility sentences, `product-plug.md` wins (no prices or plan details in soft mentions).

**Check every note against the draft before you create the Doc.** For each item with a note, find the sentence or section in `fix.md` that applies it and confirm it obeys the note. Fix `fix.md` if not. The Approval summary must describe what the draft actually does, never what the note asked for.

**Existing copy that no finding targets stays exactly as crawled**, apart from the silent fixes:
- Paragraphs over 4 sentences are split at natural break points, without changing a word.
- The silent link fixes printed in Step 1 (AI-tool tracking tags removed, minor redirects updated to their final URL).

Silent fixes aren't findings and aren't logged on the checklist.

## Step 4: Create the Fix Doc

1. **Write the Doc as markdown** to `.refresh-cache/[slug]/fix.md` with one Write call, using the markdown subset of `scripts/write_to_gdoc.py`. Wrap every new section (and every newly added paragraph, list or FAQ) in a line `<!-- new -->` before and `<!-- /new -->` after, so it's highlighted green.

   Doc structure:
   1. `# [H1]` (the confirmed H1, changed if a finding changed it)
   2. `**URL slug:** [slug]`
   3. `**Update date:** YYYY-MM-DD` (today)
   4. `**Title tag ([changed / unchanged]):** …` and `**Meta description ([changed / unchanged]):** …`
   5. `**Approval page:** [link]([approval page link])`
   6. `---`
   7. **Approval summary** (the Drive record of what was decided), three short lists, one line per item with ID and title:
      - **Applied:** every applied item, with its note if it had one
      - **Skipped:** every skipped item (Decide items answered No, Applied items set to Skip)
      - **Couldn't apply / needs a check:** anything approved that wasn't applied, with the reason (e.g. a keyword placement that would read as stuffing), a source you could not verify, a source of a different kind than the fix asked for, and anchors that will change
   8. `---`
   9. **Change checklist**, one line each, `☑` or `☐`, with section names where useful. Tick a line when at least one applied item carries its `checklist` tag (`h1`, `meta`, `new_sections`, `removed_merged`, `restructured`, `faq`, `key_takeaways`, `entities`, `outdated_info`, `links`). "Primary keyword changed" and "Funnel changed" come from `run.json` (both are normally unchanged in optimize mode):
      - Primary keyword changed
      - Funnel changed
      - H1 changed
      - Title tag / meta description changed
      - New sections added
      - Sections removed or merged
      - Sections restructured or reordered
      - FAQs refreshed
      - Key takeaways / summary block added
      - Missing entities added
      - Outdated info updated
      - Links updated
   10. `---`
   11. The clean edited copy: the post from the first block to the FAQs, with headings at their real levels (`##` H2, `###` H3; H4 and deeper as bold paragraphs). New copy wrapped in the `new` markers. Image blocks become `[TODO · SCREENSHOT: existing image: [alt text]]` so their position stays visible.
2. **Check links, convert and upload, in one Bash call:**
   ```bash
   python3 scripts/refresh_links.py --md .refresh-cache/[slug]/fix.md [slug] && python3 scripts/refresh_to_gdoc.py .refresh-cache/[slug]/fix.md .refresh-cache/[slug]/fix.html && ./scripts/gdoc_upload.sh '[Fix_[H1], cut so the title stays under 80 characters]' .refresh-cache/[slug]/fix.html
   ```
   Quote the title safely (the H1 may contain quotes or an apostrophe). The link check covers only links the draft adds (plain `curl` doesn't work on Seobility's site: it answers 403; the script sends browser headers). If it finds a problem it exits non-zero and the chain stops before the upload: `dead` or `soft_404` → replace the link with a working page from the Sitemap Cache copy (`python3 scripts/refresh_sitemap.py query [slug] --terms "…"`) or drop the link and keep the text, and list it under "Couldn't apply"; `moved` → use the final URL; `ai_tracking` or `tracking` → use the clean URL. Edit `fix.md` and run the call again. `unverified` links stay; list them under "Couldn't apply" as "couldn't be checked". Don't hand-edit the HTML.

   **When the upload succeeds, the last lines print `Created Google Doc: [URL]`. That is the Fix Doc: you are done with this step; never read or retype the HTML.**
3. **Only if the upload printed `NOT CONFIGURED` (exit 4) or `UPLOAD FAILED` (exit 5):** use the Drive connector. Print the HTML and the folder ID with `cat .refresh-cache/[slug]/fix.html; grep '^REFRESH_FOLDER_ID=' .env`, then call `create_file` with `title` = `Fix_[H1]` (cut so it stays under 80 characters), `parentId` = the `REFRESH_FOLDER_ID` value from `.env` (`grep '^REFRESH_FOLDER_ID=' .env`; omit `parentId` if it is empty), `contentMimeType` = `text/html`, `textContent` = the HTML. Mention in the reply that the upload failed or isn't set up, and why.

**Last resort:** if both the upload script and the Drive connector fail, say so, then give the markdown inline in chat.

**Reply in chat** with: the Fix Doc link, how many items were applied (by fix type), anything not applied and why, the number of placeholders by type, and "Exact cost of this run: `python3 scripts/refresh_cost.py`." Don't paste the copy in chat.

---

## Rules
- Never apply anything until the gate in Step 1 passes.
- Notes are binding and replace the fix text they contradict. Figures need a FOUND from `refresh_verify.py`.
- Decide items: only `Y` is applied. Applied items: applied unless skipped. Required items: always applied.
- Existing copy no finding targets stays exactly as crawled, except the silent fixes.
- Out of scope: editorial changes to existing copy (em dashes, UK vs US spelling, tone), technical SEO, URL slug changes.
- New copy follows the tone file, the style rules above and `product-plug.md`.
- Unconfirmed facts stay `[TODO · VERIFY: …]`, never a guessed correction.
- New copy is highlighted green (`#d9ead3`), placeholders yellow (`#f1fa8c`).
- The Fix Doc is a new Doc in the refresh folder, and the only Drive output of the refresh. Never write to the approval page from `-fix`.
- Cost rules: tools loaded once up front, independent calls in one turn, no files read that a script already printed, no token report.

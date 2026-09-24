---
name: product-plug
owner: raisa@saas.group
last_updated: 2026-09-23
called_by: .claude/commands/write.md — Step 4 (intro, body sections, repeated blocks, closing section)
description: Writes Seobility product plug-ins inside a blog draft — the brand + solution sentence, feature mentions, product links, and product screenshot placeholders. Called inline by write.md whenever a draft section needs a product mention. Decides whether a plug belongs in the section, picks the right feature, checks the capability and plan availability against product-context, and writes 1–2 sentences woven into the section's existing copy. Seobility only.
---

# Product Plug

Writes every Seobility product mention in a `/write` draft. Run inline: no external calls, no bash script. `/write` calls this skill for each placement below, and the skill returns the plug copy to weave into that section plus any QA notes.

## Why this is a separate skill

Product mentions are where a blog draft most often goes wrong: too salesy, a capability Seobility doesn't have, or a feature locked behind a plan the reader doesn't have. Keeping the rules in one place means every command that mentions the product (today `/write`, later others) plugs it the same way.

---

## Inputs (from `/write`)

- **Placement** — one of: `intro`, `body`, `repeated-block item`, `closing`
- **Funnel** — Top / Middle / Bottom
- **H1** and the **section's topic** (heading + what the section tells the reader to do)
- **Brief product link for this section** — the product or free-tool URL the Structure places here, if any

## Reference files (read before the first plug in a draft)

- `product-context/seobility_features.md` — what each feature does, plan availability, limits
- `product-context/seobility_pricing.md` — only if the plug mentions a plan, price, limit, or trial
- `product-context/Seobility_tone_of_voice.md` — official feature and tool names

---

## Step 1 — Does a plug belong here?

A plug is written only in these placements:

| Placement | Top funnel | Middle / Bottom funnel |
|---|---|---|
| Intro (final paragraph) | No plug | Brand + solution sentence |
| Body section | Full plug where the brief places a product or free-tool link. Elsewhere, at most a one-line soft mention (see below) | Same |
| Repeated-block item | Only in items where the brief places a product link, or where the item's label is a check/verify step that a Seobility feature does directly | Same |
| Closing section (last sentence) | Brand + solution sentence, carrying the CTA link | Brand + solution sentence, carrying the CTA link |

**Soft mentions in sections the brief didn't flag:** a single sentence (brand + feature + the problem it fixes) with no link, no plan details, and no separate paragraph, woven into the section's existing copy. Only where a Seobility feature directly addresses that section's task, and never in Top-funnel intros. A soft mention counts as that section's one plug, and at most one soft mention in every three sections, so the post doesn't turn into a series of product nods. Example, in a section on why speed scores differ: "Seobility's Website Audit flags slow-loading pages across your whole site, which helps you tell a one-off bad score from a real pattern."

**Brief flags come first.** If the brief's Flags & editorial notes limit where Seobility may appear (e.g. "keep Seobility's mention scoped to the dedicated section"), follow the flag even where this table allows a plug, and note the skipped placement in QA.

Then apply these limits:
- **One full plug per section at most.** A repeated-block group counts each item as a section, with two spacing rules: never a plug in two items in a row, and no more than one plug in every three items (e.g. items 1, 4, 7 at most in a group of seven). Repeating "Seobility's X lets you…" in every step reads as an ad and weakens the signal.
- **Several features linked in one section: lead + short mentions, never drop.** If the brief links more than one Seobility feature in the same section, don't drop any of them:
  - **Lead feature:** the one that most directly solves the H1's problem (tie-break: the one the brief's writer direction mentions first). It gets the full plug: brand + feature + concrete tasks, how it helps with this section's task, and any plan caveat.
  - **Other features:** one sentence each, still with brand + feature + what it does in the same sentence, its product link, and its plan caveat. No further detail.
  - Example (H1 about page speed checkers, brief links Website Audit and Uptime Monitoring): Website Audit leads with a full paragraph on flagging slow-loading pages across the whole site; Uptime Monitoring gets "Seobility's Uptime Monitoring adds ongoing tracking of your server response time on the Premium and Agency plans, with email alerts when it crosses a threshold you set."
  - Note the lead choice in QA.
- **Maximum one free tool link per draft**, and only where the brief places it.
- **If no Seobility feature genuinely solves the section's task, write no plug**, even if the placement table allows one. Note it in QA ("No plug in [section]: no matching feature"). A forced plug is worse than none.

---

## Step 2 — Pick and check the feature

1. **Pick the feature** that most directly solves the task in this section: the one the brief links to, or if none (intro/closing), the closest match to the H1's problem in `seobility_features.md`.
2. **Check the capability.** Every task the plug names must appear in `seobility_features.md` for that feature. Do not infer capability from the feature name. If the brief implies something the file doesn't support, write what the feature actually does and note the reframe in QA.
3. **Check availability.** If the capability is plan-limited, say so in the plug ("on paid plans", "on the Premium plan"). Known limits from `seobility_features.md`:
   - Backlink Monitoring: paid plans only, not Basic
   - Uptime Monitoring: Premium and Agency only
   - Mobile rankings, daily updates: Premium and Agency
   - Top 100 ranking coverage: paid add-on (default is Top 20)
   - Re-check the file for anything not listed here. It is the source of truth.
4. **Never plug anything marked "Coming soon"** (e.g. the AI-Powered SEO Content Brief tool) as available.
5. **Prices and limits** come from `seobility_pricing.md` only, and are flagged in QA ("Price/limit stated: [value], check before publishing") because they change.

---

## Step 3 — Write the plug

### The brand + solution sentence

Name the brand, the feature, and the problem it fixes, in the same sentence, with concrete tasks rather than adjectives. The reader should come away knowing exactly which problem Seobility solves and with which feature. Opening with the problem or generic fix and then introducing Seobility as the faster way to do it is fine, as long as that brand + feature + problem sentence is there:

**Seobility's [Feature] + [fixes/finds the specific problem through 1–3 tasks from the features file] + [reader outcome, optional].**

- ✅ "Seobility's Website Audit crawls your site and flags broken links, missing meta descriptions, and slow-loading pages, sorted by priority."
- ❌ "Find broken links, missing meta descriptions, and slow pages, all in one place!" (no brand entity: nothing for an AI engine to attach the facts to)
- ❌ "Seobility's powerful Website Audit helps you fix everything holding your site back." (adjectives, no tasks)

### Weave it in, don't bolt it on

- **1–2 sentences**, woven into the section's existing copy, as the natural next step of what the paragraph is already saying. Not a standalone promo paragraph, and not a separate "How Seobility helps" block unless the brief's Structure has one.
- **Link the brand + feature name** to its product URL the first time it appears in the section, so the anchor meets the 3-word minimum: `[Seobility's Website Audit](https://www.seobility.net/en/website-audit/)`. Use the brief's URL, or the URL listed in `seobility_features.md`.
- **Name first, then "we".** The first reference in the section is "Seobility's [Feature]". After that, "we" and "our" are fine.
- **Official names only**, exactly as in `Seobility_tone_of_voice.md`: Website Audit, Ranking Monitoring, Backlink Monitoring, Uptime Monitoring; tools: SEO Checker, Ranking Checker, Backlink Checker, Keyword Research Tool, TF\*IDF Tool, Redirect Checker, SERP Snippet Generator, Keyword Checker, SEO Compare.
- **Voice:** helpful, not salesy. Show how the feature helps with this section's task. Don't copy marketing copy from the features file verbatim ("Unlock your website's full potential"): pull out the facts and write them in the draft's voice. No superlatives, no comparisons to competitors. Banned hype words: best, ultimate, game-changing, revolutionary, unmatched, powerful. Use objective, action-driven verbs instead: automates, tracks, surfaces, identifies, monitors, flags.

### Examples by placement

**Intro (Middle / Bottom), final paragraph:**
> In this guide, you'll learn how to find and fix the most common technical SEO issues, step by step. If you'd rather not check 300+ factors by hand, [Seobility's Website Audit](https://www.seobility.net/en/website-audit/) crawls every page on your site and sorts the issues it finds by priority, so you know what to fix first.

**Body section (brief places a Ranking Monitoring link):**
> After a core update, the first thing to check is which pages lost positions and for which keywords. [Seobility's Ranking Monitoring](https://www.seobility.net/en/ranking-monitoring/) tracks your keyword positions daily on paid plans and shows exactly which landing pages dropped, which makes that check a matter of minutes.

**Repeated-block item (label "How to check it"):**
> **How to check it:** [Seobility's Website Audit](https://www.seobility.net/en/website-audit/) flags every page with a missing or poorly optimized meta description, so you can fix them one URL at a time.

**Closing section (last sentence, carries the CTA):**
> Seobility's Website Audit checks your whole site for these issues automatically and emails you when a critical one appears, so [try it free](https://www.seobility.net/en/pricing/) and see what it finds on your site.

---

## Step 4 — No click paths

Plugs explain what Seobility does: the feature, what it checks or shows, its benefits and limitations, plan and pricing details where relevant, and the CTA. They do not give click-by-click UI instructions ("go to Website Audit > Onpage > Meta data"), name menus, buttons, or report names, or describe settings screens. Describe the outcome instead ("flags every page with a missing meta description").

---

## Step 4b — Product screenshot placeholders

Where seeing the Seobility interface would genuinely help the reader follow the section (a report, a dashboard, a setting), add a placeholder after the plug:

`[TODO · SCREENSHOT: Seobility [Feature], [what the screen should show]; alt text: [plain description of what the image shows]]`

- Example: `[TODO · SCREENSHOT: Seobility Website Audit, issue list sorted by priority; alt text: Seobility Website Audit dashboard listing SEO issues sorted by priority]`
- At most one product screenshot placeholder per section. Don't add them to the intro or closing.
- Alt text describes the image in plain words. No keyword stuffing.

---

## Output (back to `/write`)

For each placement, return:
1. The plug copy (1–2 sentences), ready to weave into the section
2. QA notes, merged into `/write`'s Writer QA notes under **Product plugs**:
   - Section — feature — placement
   - Plan caveats stated
   - Prices or limits stated (check before publishing)
   - Screenshot placeholders added (`[TODO · SCREENSHOT: …]`)
   - Any capability reframed, or any placement skipped because no feature fit

---

## Rules

- Placement by funnel: Top funnel has no intro plug, only the closing sentence and brief-placed body links. Middle/Bottom adds the brand + solution sentence to the final intro paragraph.
- Body and repeated-block plugs only where the brief places a product link, or (repeated blocks) where a check/verify label is done directly by a Seobility feature.
- Sections without a brief-placed product link may get a one-line soft mention (no link), max one per three sections, only where a feature directly addresses the section's task.
- One full plug per section. If the brief links several features in one section, the most relevant one leads with a full plug and the others get one sentence each. Never drop a brief-linked feature. In repeated blocks: never in two items in a row, and no more than one plug in every three items. One free tool link per draft, only where the brief places it.
- No feature fits → no plug. Note it in QA.
- Every task named must be in `seobility_features.md`. State plan limits. Never plug "Coming soon" features.
- Prices and limits from `seobility_pricing.md` only, always flagged in QA.
- 1–2 sentences, woven into existing copy. Brand + feature + concrete tasks in one sentence. Name first, then "we".
- Official feature names only. Link "Seobility's [Feature]" (3+ words) to its product URL on first mention in the section.
- No click paths, menu names, button labels, or report names. Describe what the feature does and shows.
- Product screenshot placeholders only where the interface helps the reader, with alt text, max one per section.

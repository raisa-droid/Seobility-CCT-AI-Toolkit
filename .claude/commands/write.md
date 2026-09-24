# Write Command

Invoke with: `/write [paste brief]`

> **Status: draft.** Logic is still being tested with different H1s and blog types. Expect changes.

Drafts a full blog post from a content brief. Input is the brief output from `/brief`, pasted as-is. The draft follows the brief's structure, keywords, entities, and links, and is written in Seobility's brand voice. It is a first draft for human editing, not a publish-ready post.

## Dependencies
- `product-context/Seobility_tone_of_voice.md` — brand voice rules (Step 1)
- `product-context/Seobility_brand_summary.md` — positioning and ICP (Step 1)
- `skills/product-plug.md` — every product mention, run inline (Step 4)
- `product-context/seobility_features.md` — product capability check, used by the product-plug skill (Steps 1, 4)
- `product-context/seobility_pricing.md` — only if a plug mentions plans, limits, or trial details (Step 4)
- `web_search` / `web_fetch` — external data sourcing and fact verification (Step 2)
- `scripts/write_to_gdoc.py` — converts the markdown draft into Google-Docs-ready HTML (Step 6)

No scripts.
- Google Drive MCP — creates the draft as a Google Doc in the drafts folder (Step 6). Falls back to inline chat output if not connected.

---

# Seobility's Write Skill

## Purpose

Turn a single `/brief` output into a full first draft of a blog post for Seobility's English-language blog. The brief has already done the research and structure work. This skill writes to that brief. It does not re-research the topic, restructure the piece, or change the angle.

---

## Required inputs

The skill accepts the `/brief` output pasted in full. It parses flexibly: the brief may be copied from chat with formatting lost, edited by hand, or trimmed. Missing fields are flagged after parsing. Blocking fields stop execution, non-blocking fields are skipped or filled with a placeholder.

**Blocking (skill cannot proceed without these):**

- `H1` — the `#` heading at the top of the brief
- `Funnel` — Top / Middle / Bottom
- `Primary KW`
- `Structure` — the H2/H3 skeleton with writer direction

**Non-blocking:**

- `Search intent + SERP format` — if missing, infer the format from the Structure (a tool list is a listicle, and so on) and flag it
- `Meta title` / `Meta description` / `URL slug` — carried into the output header as-is if present, omitted if not
- `Seed KW`, `Secondary KWs`, `Contextual KWs` — used where present
- `Word count` — if missing, target 1,500–2,000 words and flag it
- `Reader` and `Core idea` — if missing, derive from H1 + Funnel + Structure and flag it
- `Entities` (inline per section) — used where present
- `Real-world context from Reddit` — used where present, skipped if absent
- `Flags & editorial notes` — applied where present
- `Internal links` — placed where present, skipped if absent or marked "not available"
- `CTA` — defaults to https://www.seobility.net/en/pricing/ if missing
- `External references` — used where present, never generated

If a blocking field is missing, stop and ask for it. Do not infer blocking fields from context.

---

## Parsing behaviour

After parsing, output this confirmation block before drafting:

```
Parsed brief:
- H1: [value]
- Funnel: [value] | Format: [value]
- Primary KW: [value]
- Word count target: [value or MISSING — using 1,500–2,000]
- Structure: [n] H2s, [n] H3s
- Reader / Core idea: [confirmed or MISSING — derived from structure]
- Contextual KWs: [n or MISSING]
- Internal links: [n or MISSING — none will be placed]
- Reddit scenarios: [n or MISSING — none will be used]
- Flags: [n or No flags]
- Repeated blocks: [section group + labels from brief, or "none specified"]

Drafting now.
```

Do not ask for confirmation after the parsing block. Proceed immediately.

---

## Step 1 — Load voice and product context

Read these before writing a single sentence:

1. `product-context/Seobility_tone_of_voice.md` — the rules for voice, do's and don'ts, and official feature names. This is the main style reference for the draft.
2. `product-context/Seobility_brand_summary.md` — ICP and positioning. Most readers are not SEO experts, and SEO is not their main job.
3. `product-context/seobility_features.md` — what each Seobility feature actually does.
4. `skills/product-plug.md` — the rules for every product mention in the draft.

Hold these as working context. Do not summarize them to the user.

---

## Step 2 — External data and fact verification

Unlike `/brief`, `/write` sources its own external data. Run both parts below before drafting. Do not pause for user selection: use what qualifies and list it in the Writer QA notes.

### 2a — Source external data (statistics, studies)

1. From the Structure, identify the claims that would be stronger with a number or a study behind them (e.g. how common a problem is, how much a factor affects rankings or traffic, how users behave in AI search).
2. For each, run `web_search` to find supporting data. Aim for **2–4 data points** across the post. A data point must support a specific claim in the section it lands in. No decorative stats.
3. **Source rules:**
   - **Original source only.** Link the study, report, official documentation, or dataset itself (e.g. Google Search Central, Google's own research, a university or independent research body, an industry survey from its publisher). Never cite an aggregator or a "100 SEO statistics" roundup. If a roundup points to a stat, trace it to the original and cite that, or drop it.
   - **Recency.** Published within the last 3 years, preferring the last 2. Drop anything older, even if it is widely quoted.
   - **No competitors (preferred).** Avoid studies published by Seobility competitors: SE Ranking, Ubersuggest, Mangools, Serpstat, Morningscore, Semrush, Ahrefs, Moz, Screaming Frog, Surfer SEO, Majestic (from `Seobility_brand_summary.md`). Look for a non-competitor source first. If a competitor study is the only credible source for a claim that matters, it may be used, but it must be flagged in the Writer QA notes.
4. **Verify every number.** Run `web_fetch` on the source page and confirm the exact figure, year, and context (sample, region, what was measured). If the figure cannot be confirmed on the source page, do not use it.
5. **In the draft:** state the source and year in the sentence and link the source inline, e.g. "A [2025 study by X](https://…) found that…". Report the figure exactly as the source does, with its context. Do not round, extrapolate, or generalize beyond what was measured.

### 2b — Verify other factual claims

The brief's writer direction sometimes calls for other specifics: a Google guideline, a definition, a threshold, a date. For each one the draft will state as fact:

1. If the brief supplies it (in writer direction or External references), use it.
2. If not, verify it against a primary or authoritative source: find it with `web_search`, then confirm it on the source page with `web_fetch`. A search snippet alone doesn't count as confirmed, even from the official domain.
3. **Third-party tool pricing and plan details** (listicles and comparisons) are often behind pages that block fetching. If a price, plan limit, or trial length can't be confirmed on the tool's own site, leave it as a VERIFY placeholder for a human to check. Never fill it from review or aggregator sites.
4. If it cannot be verified, do not state it. Rewrite the sentence without the specific claim, or insert a placeholder: `[TODO · VERIFY: claim + where to check]`.

**Confirmed vs. believed.** SEO is full of ranking-factor claims that Google never confirmed. Match the wording to the evidence:
- **"Google confirms / Google says…"** only with a link to Google's own documentation or an official Google statement (Google Search Central, the Search Central blog, a named Google spokesperson on record).
- **"Studies suggest… / A [year] study by X found…"** for third-party research, with the source linked (Step 2a rules).
- **"Many SEOs believe… / A common view is…"** for widely held but unconfirmed practice. Never present these as fact.
- If Google has explicitly said something is *not* a ranking factor, don't imply that it is.

### 2c — Confirm internal link targets

For every URL in the brief's Internal links list, run `web_fetch` and note the page's actual H1 and topic. Don't infer the topic from the slug. The anchor text in Step 4 is built from this confirmed topic. If a URL is broken, redirects somewhere unexpected, or covers a different topic than the brief assumed, still place it only if it genuinely fits, and note the problem in the QA notes under Deviations from brief.

Rules for this step:
- External data supports the brief's structure. Do not add new sections, angles, or subtopics from what you find.
- Never invent statistics, study results, percentages, quotes, customer stories, or Seobility test results.
- External links in the draft are limited to: sources from 2a and 2b, the brief's External references, Reddit threads (Step 4), and, in listicles and comparisons, a tool's own official docs or pricing page (max 1–2 per tool). No other external links.

---

## Step 3 — Lock the outline

Take the Structure section as the outline.

- **Order and scope are fixed.** Keep every H2 and H3 in the order the brief gives. Do not add, drop, merge, or reorder sections. The one addition is the Key takeaways block after the intro (Step 4), which is always added.
- **Heading copy may be tightened.** The brief marks the skeleton as "Suggested" and asks for each heading to be optimized for SEO/AEO. You may rewrite heading copy for clarity, search phrasing, or question form, as long as the meaning and scope stay the same.
- **Title case for every heading** (H1, H2, H3, including Key Takeaways, FAQs, and the FAQ question H3s). Capitalize every word except articles (a, an, the), coordinating conjunctions (and, but, or, nor, for, so, yet), and prepositions of three letters or fewer (to, of, in, on, at, by, for, via), which stay lowercase unless they are the first or last word. Short verbs and pronouns are capitalized (Is, Do, You, It). Prepositions of four letters or more are capitalized (About, With, Into, Between). Keep brand and product names as written (GTmetrix, WebPageTest, Seobility's Website Audit). Examples: "Why Page Speed Test Scores Differ Between Tools", "How Seobility Fits Into Your Page Speed Workflow", "What Is the Best Tool for Testing Website Speed?", "FAQs About Page Speed Checkers".
- **Headings describe the section.** Each H2/H3 names the specific subtopic it covers, so someone reading only the headings understands the post. No generic labels ("Overview", "Our approach", "Final thoughts").
- **Keywords in headings (not too strict):**
  - Only the Primary KW and Secondary KWs may be used in headings. Contextual KWs stay in body copy.
  - The H1 already contains the Primary KW (from Sera). Keep it.
  - Use the Primary KW or a close variant in at least one H2.
  - Other H2s/H3s may use the Primary KW again or a Secondary KW, but only where the keyword fits that section's topic. Where it fits, prefer question form (e.g. "How long does a website audit take?").
  - A heading that reads awkwardly with a keyword gets no keyword. Readability wins.
- **No heading repeats the H1 verbatim.** If the brief gives an H2 identical to the H1 (common for listicle sections), paraphrase it and keep the Primary KW (e.g. H1 "7 Best Page Speed Checker Tools to Test Your Website" → H2 "Our Top 7 Page Speed Checker Tools, Reviewed").
- **FAQs H2:** `FAQs About [Primary KW or a Secondary KW]`, e.g. "FAQs About Page Speed Checkers". The question H3s under it keep the brief's wording, with grammar fixes and title case.
- **Comparison table** (tool listicles and comparisons) stays where the brief puts it, with the columns the brief specifies.

### Repeated blocks

Some posts have a group of 3 or more parallel sections: the steps of a how-to, the tools in a listicle, the mistakes in a mistakes post. Give every item in the group the same internal structure, so readers can scan it and AI engines can extract each item as a clean block.

1. **Repeated blocks are decided by `/brief`, not `/write`.** Look for a `Repeated block:` line in the brief (usually in italic under the parent H2, or in a Format note in Flags & editorial notes; it may also be added by hand). If there is one, use its labels exactly, in its order, for every item in that group.
2. **If the brief has none, don't add one.** Write the sections as normal prose under their headings. If the Structure has 3+ parallel sections that would clearly benefit from a shared structure, note it in the QA notes under Deviations from brief ("No repeated block specified for [H2]; consider adding one in /brief"), but don't change the draft's structure.
3. **Format.** Labels are bold lead-ins at the start of a paragraph or list item (e.g. `**Watch out for:** …`), never H3/H4 headings. Label-style headings like "The fix" say nothing on their own and clutter the heading outline.
4. **Each item opens with a direct 1–2 sentence answer** before the first label, so the item stands alone as a citable block.
5. **Every label carries real, specific detail**: settings, thresholds, examples, edge cases, or the exact place to check something. This depth is the information gain that makes the page worth visiting. The answer block is always complete. Never hold information back or write a deliberately partial answer to force a click.
6. **Consistency.** Same labels, same order, in every item of the group. If a label genuinely doesn't apply to one item, drop it for that item rather than padding it, and keep the rest in order.
7. **Product mentions inside repeated blocks** are written with `skills/product-plug.md`: only in items where the brief places a product link or a Seobility feature directly does the check, never in two items in a row, and no more than one plug in every three items.

---

## Step 4 — Draft

Write the full post section by section, following these rules.

### Intro (before the first H2)
- **Intro style:** pick one of these three, whichever fits the brief's core idea and reader best. Don't note the choice in the QA notes.
  - **APP (Agree → Promise → Preview):** start from something the reader already knows or has experienced, then say what the post delivers and outline the route. The default for most posts. An optional problem hook between Agree and Promise is fine when the brief's core idea has one (e.g. "two page speed checkers can give the same page very different scores").
  - **PAS (Problem → Agitate → Solution):** name the problem, show what it causes, then present the post as the solution. Keep the agitation factual (what happens), never fear, guilt, or exaggerated stakes. Best when the reader has an active problem, often in Bottom-funnel posts.
  - **Myth-busting:** state a common belief, then correct it with the fact, then say what the post covers. Use it when the brief's core idea challenges a belief (e.g. "Duplicate content doesn't get your site penalized. Google usually picks one version and filters the rest.").
  - Don't use other intro styles: no Before–After–Bridge, data-hook, answer-first (BLUF), AIDA, story-hook, or question-hook openings.
- 80–150 words. No heading.
- **No links in the intro.** Link placement starts from the first H2.
- Middle / Bottom funnel only: the final paragraph of the intro includes the brand + solution sentence, written with `skills/product-plug.md`. Top funnel intros do not mention Seobility.
- Use the Primary KW within the first 100 words, naturally.
- Open on the reader's situation or question from the brief's `Reader` field, then say plainly what the post will give them. No throat-clearing ("In today's digital landscape…").
- **Name the reader's world in the first paragraph.** The first paragraph on its own should make clear who the post is for and what it's about (e.g. therapists and their practice, not a generic "you have a website" opening that could fit any business).
- Define the main topic in a plain "[Topic] is…" sentence within the intro or, at the latest, the first paragraph of the first H2, **only when the brief's Reader wouldn't already know the term** (e.g. "duplicate content" for beginners). Skip it when the term is self-explanatory to that reader (e.g. "therapist marketing" for therapists) or when the topic is a task rather than a concept, and state what the post or task achieves instead.

### Key takeaways (directly after the intro)
- Always added, even though the brief does not list it.
- Heading: `Key Takeaways: [paraphrase of the H1 that includes the Primary KW]`, in title case, e.g. H1 "7 Best Page Speed Checker Tools to Test Your Website" → "Key Takeaways: Top Page Speed Checker Tools Compared".
- 3–5 bullets. Each bullet is one self-contained fact or instruction from the post that makes sense without reading the rest (no "as explained below").
- Bullets deliver the H1's promise: what the reader should choose, do, or know to act. Use specifics where the post has them (named tools, thresholds, steps). A statistic belongs here only if it changes the reader's decision; background stats (e.g. how many sites fail a metric) stay in the body. No new claims that the body does not support.
- No links in Key takeaways.

### Body sections
- **Answer first.** Open every H2 with 1–2 sentences that directly answer or summarize the section, so the passage can stand alone for AI extraction. Expand after that.
- **Follow the writer direction.** Every instruction in a section's direction must be carried out in that section. This is the brief's contract with the writer.
- **Self-contained paragraphs.** Each paragraph should make sense if an AI engine lifts it out alone. No "as mentioned above" or "see the previous section". Don't open a paragraph with "it", "this", or "they" when the thing it refers to is in an earlier paragraph: name it again. No vague pointers like "start here", "this one", or "the above": name the thing and the situation ("Start with Google PageSpeed Insights when you want to check your page speed health"). Specific wording is what AI engines can quote.
- **Complete sentences.** No sentence fragments. After a colon that introduces a definition, either continue the same sentence or write a full sentence ("Render-blocking resources are CSS and JavaScript files that…"), never a standalone noun phrase ending in a period.
- **Specifics over adjectives.** Where a claim could carry a number, a date, a proper noun, or a concrete noun, use it (from the brief, `product-context/`, or Step 2 data). Replace vague modifiers ("many", "thousands of", "recently", "powerful", "leading", "scalable", "flexible", "world-class", "innovative", "best-in-class") with the fact, or cut them. Never invent the fact to fill the gap.
- **One claim per sentence** in the parts AI engines extract most: the answer-first opener under each H2, Key takeaways bullets, and FAQ answers. If one of those sentences joins several claims with "and", split it. Body copy elsewhere can keep a natural rhythm.
- **Lists.** Items are specific, complete phrases with parallel structure, not single vague words.

### Match the format to the question
Format each section's answer the way Google and AI engines extract it for that kind of question. The answer-first opener still comes first. The format applies to what follows it.

| Question type | Format | Example |
|---|---|---|
| **Definition** ("What is…") | A 40–60 word paragraph starting "[Term] is…", then detail | H2 "What is crawl budget?" → "Crawl budget is the number of pages Googlebot crawls on your site within a given time. It depends on how fast your server responds and how much Google wants to crawl your content…" |
| **How-to** ("How to…") | One-sentence answer, then a numbered list. Each step starts with a verb | H2 "How to fix broken internal links" → "Find them with a crawl, then update or redirect each one." then 1. Run a crawl… 2. Export the list of broken links… 3. Update the link or set a 301 redirect… |
| **Comparison** ("X vs. Y") | One-sentence difference, then a table | H2 "Noindex vs. robots.txt disallow" → "Noindex keeps a page out of search results, while disallow stops Google from crawling it." then a table with rows: what it does, when to use it, effect on crawling, effect on indexing |
| **Yes/no** ("Does… / Is… / Can…") | Start with "Yes", "No", or "It depends", then the one-sentence reason | H2 "Does page speed affect rankings?" → "Yes, but mostly as a tiebreaker. Google uses Core Web Vitals as part of its page experience signals…" |
| **Duration or amount** ("How long… / How much…") | The range or number first, then what it depends on | H2 "How long does SEO take?" → "Most sites see first results within 3–6 months [TODO · VERIFY: source]. How fast depends on…" |
| **List / best** ("Best… / Types of…") | One-line lead-in, then a list with a one-line verdict or definition per item | H2 "Types of redirects" → "There are four redirect types you'll use most:" then **301:** permanent… **302:** temporary… |

These examples show the pattern only. Facts in them still go through Step 2.

### Keywords and entities in body copy
- **Primary KW:** within the first 100 words of the intro, and once in the closing section. In the body, watch for generic references that the Primary KW can naturally replace, and swap some of them, not all. This works when the Primary KW is a noun phrase that stands in for a generic word: "page speed checker" replaces "tool" ("which page speed checker", "these page speed checker tools"). It often doesn't work when the Primary KW is a question, a task, or a long phrase ("how to improve page speed", "what is crawl budget"). In that case, don't force it: use it where a sentence genuinely talks about that exact thing, and rely on close variants elsewhere. These swaps are opportunities, not a quota. If the Primary KW offers few natural swaps, say so in the QA notes. Elsewhere, use variants and synonyms rather than repeating the exact phrase.
- **Secondary KWs:** each used at least once in the body. When a Secondary KW is in a heading, use it (or a close variant) in that section's body too. A Secondary KW that isn't in any heading goes, exact or near-exact, in the first paragraph of the section most related to it: search engines and AI engines weigh a section's opening most when deciding what it covers.
- **Contextual KWs:** body copy only, each at least once, in the section where it fits the topic best.
- **Entities:** every entity in a section's italic `Entities:` list appears in that section. Explain each one in plain words the first time it appears (e.g. "crawl budget, the number of pages Googlebot will crawl on your site in a given time"). Mention it alongside the related terms and entities in the same section, so search engines can see how the concepts connect. Remove the italic entity lines from the draft itself.
- **Tie every entity to an action or outcome.** Never drop an entity as a standalone definition. Explain it inside a sentence about what the reader does with it or what it causes.
  - ❌ "Render-blocking resources are CSS and JavaScript files. Render-blocking resources slow down pages."
  - ✅ "If a page stays blank for a second before anything appears, render-blocking resources are a common cause: CSS and JavaScript files the browser must finish loading before it can show the page."
  - Branded or named entities (Google Search Console, Core Web Vitals, Lighthouse) use their exact name, never an invented synonym.
- **Topical terms.** Use the everyday vocabulary of the topic and of the reader's world, even when those words aren't in the keyword list. They tell search engines what the page is really about, and they make the copy sound written for insiders. Take them from the topic itself and from the brief's Reader field. There are two kinds:
  - **Topic vocabulary:** the verbs and concepts that come with the subject. Metrics and reporting: measure, calculate, benchmark, baseline, ROI, KPI, trend, report. Technical SEO and site audits: crawl, index, render, status code, redirect chain, prioritize, fix.
  - **Reader vocabulary:** the nouns of the reader's own world. Agencies and freelancers: clients, retainer, client reporting, white label, onboarding.
  - Use them where they read naturally. They're not keywords to repeat or place in headings.
- Never force a keyword into a sentence where it reads awkwardly. Never bold keywords. No keyword stuffing: if a phrase starts to feel repetitive when read aloud, swap in a variant.
- **Real-world context.** Where a Reddit scenario is tagged to a section ("recommend using in: [H2]"), use it in that section as a real example. Paraphrase it or quote a short passage (one or two sentences) from the thread, and link to the thread using its source URL from the brief, e.g. "One [small business owner on Reddit](https://www.reddit.com/…) described…". Never name the username. After each Reddit mention, insert `[TODO · SCREENSHOT: add screenshot of this Reddit thread: [thread URL]; alt text: …]`, with the thread's full URL (so the editor doesn't have to look it up in the brief) and suggested alt text that describes what the thread shows in plain words. The screenshot keeps the example intact if the post is later deleted or removed.
- **Listicles (E-E-A-T).** If the brief includes the E-E-A-T writer note, write tool entries in an evaluated voice ("our take", "what stood out", "best for"). Do not invent hands-on test results, scores, or observations. Where a first-hand detail would strengthen an entry, insert `[TODO · TEAM: add first-hand observation, e.g. …]` for the editor to fill.
- **Formatting.** Short paragraphs (2–4 sentences, about 70 words at most), including paragraphs inside repeated-block labels. Split a longer paragraph at its natural break: where the focus shifts to a new point, feature, or example, not mid-argument. Use numbered lists for steps and bulleted lists for sets of items. Use a table only where the brief calls for one or where it clearly beats prose for comparison. Bold sparingly, for key terms on first use only.

### Product mentions and links
- **All product mentions are written with `skills/product-plug.md`.** Read it before drafting and run it inline (no external call) for every placement it covers: the final intro paragraph (Middle/Bottom), body sections where the Structure places a product or free-tool link, repeated-block items, and the last sentence of the closing section. The skill decides whether a plug belongs, picks and checks the feature, and returns 1–2 sentences to weave into the section's existing copy, plus QA notes.
- Do not write product mentions outside the skill, and do not add product mentions the brief and the skill don't call for.
- **Don't re-cover linked pages.** When a subtopic has its own page in the brief's Internal links (e.g. a full post on canonical tags), cover it in 1–2 sentences woven into the existing copy and link to that page, instead of writing a mini version of it. If the brief's writer direction explicitly asks for that subtopic in depth, follow the brief and note the overlap in QA.
- **Internal links:** place every URL in the brief's Internal links list once, in the section where it fits best (use the Structure's placement notes where given). Build the anchor from the target page's confirmed topic (Step 2c), not the slug: 3–6 words, exact-match or near-exact-match to that page's main keyword where it reads naturally. Each anchor is unique to its destination: never use the same anchor phrase for two different URLs. Never "click here", "learn more", or a bare URL. When two linked pages look similar (e.g. a blog post and a use case page on the same topic), write anchors that make the difference obvious, so readers don't think the same page is linked twice.
- **All anchors are at least 3 words**, internal and external ("Google's PageSpeed Insights documentation", not "Google's documentation" or "page speed").
- **Link format:** markdown links with full URLs, e.g. `[Website Audit](https://www.seobility.net/en/website-audit/)`.

### FAQs
- **Neutral, encyclopedic tone** in FAQ answers: no "we", "our", or "you'll love". This is a flat exception to the brand voice, because answer engines lift FAQ answers on their own. The rest of the post keeps the Seobility voice.
- Answer each question in 2–3 sentences, 40–60 words. The first sentence answers the question directly. No preamble, no "Great question".
- Each answer contains at least one concrete detail (a number, named tool, threshold, or timeframe) where the topic allows.
- Each answer must work on its own, without the rest of the post.
- FAQ answers should not repeat body copy word for word. Add something new, or give the tightest version of the answer.

### Closing section
- The last section before the FAQs (after the final body H2). If the post has FAQs, they are always the final section, after the closing section. Its heading carries a Primary or Secondary KW variation (e.g. "Turn Your Page Speed Checker Results Into Faster Pages"), never a bare "Conclusion", "Final Thoughts", or "Key Takeaways" (that heading is used after the intro). A brand CTA heading (e.g. "Keep Your Page Speed in Check With Seobility") is allowed only when the topic ties directly to a Seobility product, meaning the brief places at least one product link.
- 80–150 words, including the Primary KW once: recap the one or two things the reader should do next, then end with the brand + solution sentence from `skills/product-plug.md` (all funnels), carrying a single CTA link to the brief's CTA URL, framed as a helpful next step. Encouraging, never guilt- or fear-based.

### Placeholder format
Every spot that needs human work uses one format, so editors can find them all by searching for `[TODO`:

`[TODO · TYPE: what to do]`

- Types: `VERIFY` (a fact to check), `TEAM` (first-hand input needed), `SCREENSHOT` (an image to add, with alt text after `; alt text:`).
- Always single square brackets, always the `TODO ·` prefix (TODO, space, middle dot "·", space), then the type, a colon, and the message. Not bold. In the Google Doc, the highlight makes them stand out. No em dashes or pipes inside placeholders (pipes break markdown tables).
- The Writer QA notes give placeholder counts by type only (e.g. "VERIFY ×12, TEAM ×4, SCREENSHOT ×2"). The highlighted placeholders in the draft carry the details.

### Voice and style (applies throughout)
- Friendly, warm, professional, encouraging, per `Seobility_tone_of_voice.md`.
- Address the reader as "you". Seobility is "we" and "our" where it speaks.
- Beginner-friendly: explain any technical term the first time you use it, in plain words. Short sentences. Active voice.
- No exaggerated claims, no overpromising ("guaranteed rankings", "dominate the SERPs").
- No AI filler: avoid "delve", "dive in", "unlock", "unleash", "elevate", "leverage", "game-changer", "in today's fast-paced digital world", "it's important to note that", "navigating the landscape", "robust", "seamless", "actually", "harness", "comprehensive" and "holistic" (as filler adjectives), "look no further", "overall", "to sum up".
- No AI patterns either: "Whether you're a beginner or a pro…", "It's not just X, it's Y", "In conclusion", "At the end of the day", rhetorical-question openers ("Ever wondered why…?"), reflexive groups of three (use as many items as there really are), and ending every section with a one-line summary of what it just said. Vary sentence length and paragraph openings.
- No announcer transitions that introduce the brand or the next point instead of making it: "This is where Seobility comes in", "That's where X helps", "Enter X", "The checking part is where…". Make the point directly.
- **Sentence starters:** within one section, the same word shouldn't start more than two sentences (e.g. not "Seobility… Seobility… Seobility…" or "You… You… You…").
- Also banned: staccato fragment stacking ("Better rankings. Faster fixes. Less guesswork."), the parallel-comparison-then-label pattern ("X is for A. Y is for B. That's the difference."), and the corrective "That's not X, that's Y".
- **Explicit dates, not relative time.** Write "Since the March 2024 core update", not "recently", "this year", "lately", or "nowadays". Undated time words go stale and give AI engines nothing to extract. Verify dates per Step 2b.
- **Evaluating competitor or third-party tools (listicles and comparisons only):**
  - Frame weaknesses as fit, never as "bad" or "useless": "[Tool] excels at [strength], but may be a stretch for teams that need [specific need]."
  - Default to attribution phrasing for cons ("Users frequently report…", "A common trade-off for smaller teams is…"), but only for feedback that exists in a verified source: the brief's Reddit data, or a public page fetched in Step 2. Never invent reviews, quotes, or complaints.
  - Reserve external links for specific or disputable claims, at most 1–2 per tool, and link the tool's own official docs or pricing page rather than third-party review sites.
- **Competitors.** Outside listicles and comparisons, don't name Seobility competitors (see `Seobility_brand_summary.md`) unless they are in the brief's entity lists. Never disparage a competitor. Never link to competitor domains, except their studies under the Step 2a flag rule.
- No em dashes. Use commas, colons, parentheses, or separate sentences instead.
- No emojis in blog copy.
- American English spelling and usage.

### Length
- Aim for the brief's word count range. Landing within ±10% is fine. Don't pad to reach the range, and don't cut required writer direction to stay under it. If covering every direction needs more words, go over and note it in QA.

### Brief flags
- Apply every item in Flags & editorial notes. Cannibalization scoping notes limit what the draft covers. Framing and Format notes are followed exactly.
- **Brief flags override the defaults** in this command and in `skills/product-plug.md`. Example: the skill places a brand sentence in Middle-funnel intros, but if a Framing flag keeps Seobility inside a dedicated section, the intro gets no plug. Note every override in the QA notes under Deviations from brief.

---

## Step 5 — Self-check, then output

Before outputting, check the draft against this list silently and fix anything that fails:

- Every H2/H3 from the brief is present, in order
- Every writer direction item is carried out
- Key takeaways block present after the intro, 3–5 self-contained bullets
- First paragraph names the reader's world. Main topic defined early only if the Reader wouldn't already know the term
- Every section entity appears in its section, explained on first use
- Primary KW in the H1, the first 100 words, at least one H2, and the closing section. Natural swap opportunities for generic words used where the KW allows it
- No heading repeats the H1. Key Takeaways heading is "Key Takeaways: [H1 paraphrase with Primary KW]". FAQs heading is "FAQs About [KW]". All headings in title case
- Closing section comes before the FAQs. FAQs are the final section
- No links in the intro or Key takeaways. Every anchor is at least 3 words
- No paragraph over about 70 words or 4 sentences. No fragments. No vague pointers ("start here")
- Only Primary and Secondary KWs in headings. Contextual KWs in body only. Every Secondary and Contextual KW used at least once
- Every H2 opens with a direct 1–2 sentence answer. No paragraph depends on "as mentioned above" or an unclear "it"/"this"
- No vague modifiers where a fact could go. One claim per sentence in H2 openers, Key takeaways, and FAQ answers
- FAQ answers are 40–60 words, answer first
- Each section's format matches its question type (definition, how-to, comparison, yes/no, duration, list)
- "Google confirms" only with a Google source. Unconfirmed practice is worded as belief, not fact
- Subtopics with their own internal link page get 1–2 sentences + the link, not a mini-post
- Closing heading carries a KW variation (brand CTA only for product-relevant topics). No word starts more than two sentences in one section. Secondary KWs not in a heading appear in the first paragraph of their section
- No relative time words ("recently", "this year"). No unflagged competitor names or links. No AI patterns
- Every internal link placed exactly once, anchor built from the target's confirmed topic (Step 2c), 3–6 words, unique per destination
- FAQ answers neutral and encyclopedic, no first person
- Every entity tied to an action or outcome, never a standalone definition
- Competitor tools framed by fit; attribution phrasing only for verified feedback
- Every product mention was written with `skills/product-plug.md` and passes that skill's rules
- No invented facts, stats, quotes, or test results. Anything unverified is a VERIFY placeholder
- Every external stat is from an original source, published within 3 years, verified on the source page, and linked inline with its year
- Every Reddit mention links its thread, names no username, and is followed by a SCREENSHOT placeholder that includes the thread URL
- Repeated blocks: same bold labels in the same order in every item, answer first, no label headings, no held-back information
- No em dashes, no banned filler phrases, no emojis
- Word count is within range, or the reason it isn't is noted

**Output format:** the draft is delivered as a Google Doc in the drafts folder (Step 6). The document content, in this order:

**Meta title:** [from brief, verbatim]
**Meta description:** [from brief, verbatim]
**URL slug:** [from brief, verbatim]

---

**Seed KW:** [from brief]
**Primary KW:** [from brief]
**Secondary KWs:** [kw], [kw], [kw]

---

# [H1]

[Intro]

## [H2]
...

[Full draft through the closing section and CTA, then FAQs as the final section]

---

**Writer QA notes**

- **Word count:** [actual count] vs target [range]
- **Meta title length:** [only if the meta title is over 60 characters: "[n] characters, over 60, may be truncated in search results". Flag only, do not rewrite. Omit this line otherwise.]
- **Placeholders to resolve:** [counts by type only, e.g. "VERIFY ×12, TEAM ×4, SCREENSHOT ×2", or "None". The highlighted placeholders in the draft carry the details]
- **Sources:** [one list of every external source used, one line each: source name (and year for studies), URL, what it confirms, and the section that uses it. Only sources confirmed on the fetched source page go here. This list is a record, not a to-do: anything that couldn't be fully confirmed is a VERIFY placeholder in the draft instead. If no stat met the source rules, say so here]
- **Competitor sources:** [any stat from a competitor-published study, with why no non-competitor source was used, or "None"]
- **Reddit threads linked:** [URL and section, or "None"]
- **Product plugs:** [from `skills/product-plug.md`: section, feature, placement, plan caveats, prices/limits stated, placeholders, reframes or skipped placements, or "None"]
- **Deviations from brief:** [a list; use nested bullets where a category has several items, or "None":
  - **Headings reworded:** one child bullet per heading, `"original" → "new"`
  - **Added sections:** e.g. Key Takeaways, closing section
  - **Brief flags that overrode a default rule**
  - **Directions that could not be followed**, and why
  - **Product claims reframed**
  - **Repeated blocks** the brief didn't specify but the structure would benefit from (suggestion for /brief only)]

Omit any Meta title / Meta description / URL slug / keyword line that was not in the brief. Contextual KWs are not listed in the keyword block.

---

## Step 6 — Create the Google Doc

**Drafts folder:** `1zioKWOwUMMr_n_QjziohqQ1rRHbQTFyE` (temporary "Draftwell" folder for testing `/write`; replace with the team folder ID before rollout)

1. **Write the document as markdown** to `.write-drafts/[url-slug].md` (the slug from the brief's URL slug; the folder is gitignored). Use this markdown subset so the converter can read it:
   - `#` for the H1, `##` for H2s (Key Takeaways, body H2s, closing, FAQs), `###` for H3s. Never shift levels.
   - Paragraphs separated by a blank line. `**bold**`. Links as `[anchor](https://full-url)`. Bare URLs are fine in the Writer QA notes.
   - `---` on its own line for each divider.
   - Tables in pipe format with a header row and a `|---|` separator row.
   - Lists with `- ` or `1. `. Nest by indenting child items 2 spaces. In the Writer QA notes, every field is its own `**Label:**` paragraph followed by its content, so items never read as if they belong to the field above.
   - Placeholders exactly as `[TODO · TYPE: message]`.
2. **Convert it:** run `python3 scripts/write_to_gdoc.py .write-drafts/[url-slug].md .write-drafts/[url-slug].html`. The script applies all Google Docs formatting: heading levels, 1.15 line spacing with 10pt paragraph gaps, the `#f1fa8c` placeholder highlight, dividers that don't merge into headings, nested lists, and table styling. Don't hand-write or edit the HTML. If the output looks wrong, fix the markdown and run the script again.
3. **Create the file** with the Google Drive connector's `create_file`: `title` = the H1 only, `parentId` = the drafts folder ID, `contentMimeType` = `text/html`, `textContent` = the full contents of the `.html` file. Let it convert to a Google Doc (don't disable conversion).
4. **Reply in chat** with: the parsing confirmation block (already shown), the Doc link, the word count, and the number of placeholders by type. Do not paste the full draft in chat.
5. **Fallback:** if the Google Drive connector is not connected or `create_file` fails, say so, then deliver the markdown from step 1 inline in chat (headings with `#`, `##`, `###`), with placeholders in the same `[TODO · …]` format.

---

## Rules

- Cannot proceed without all blocking fields (H1, Funnel, Primary KW, Structure). Ask for missing blocking fields before drafting.
- Parse flexibly. Do not require a fixed input format.
- Output the parsing confirmation block, then draft immediately without asking for confirmation.
- Always load `Seobility_tone_of_voice.md`, `Seobility_brand_summary.md`, and `seobility_features.md` before drafting.
- The brief is the contract. Do not add, remove, merge, or reorder sections. Heading copy may be tightened for SEO/AEO without changing scope. The only added section is Key takeaways, directly after the intro.
- Headings: only Primary and Secondary KWs, only where they fit the section's topic, question form preferred. Primary KW in the H1 and at least one H2. Contextual KWs in body copy only.
- Flag a meta title over 60 characters in the QA notes. Do not rewrite it.
- Brief flags override the default rules of this command and of `skills/product-plug.md`. Note each override in the QA notes.
- Third-party tool pricing that can't be confirmed on the tool's own site stays a VERIFY placeholder. Never use aggregator pricing.
- All headings (H1, H2, H3, FAQ questions included) use title case: every word capitalized except articles, coordinating conjunctions, and prepositions of three letters or fewer (unless first or last).
- No FAQPage schema output.
- Do not re-research the topic. `web_search` / `web_fetch` are for sourcing external data (Step 2a) and verifying specific claims (Step 2b) only.
- Always run Step 2a. Use 2–4 data points, each supporting a specific claim. Original sources only, never aggregators or stat roundups. Published within the last 3 years, preferring 2. Every figure verified with `web_fetch` on the source page, stated with its source and year, and linked inline. Do not pause for user selection.
- Avoid competitor-published studies. If one is used, flag it under Competitor sources in the Writer QA notes.
- Never invent statistics, studies, quotes, customer stories, or Seobility test results. Unverifiable claims become VERIFY placeholders or are cut.
- External links are limited to Step 2 sources, the brief's External references, Reddit threads, and (listicles/comparisons only) a tool's own official docs or pricing page, max 1–2 per tool.
- Every internal link in the brief is placed exactly once with descriptive anchor text. 
- All product mentions (brand + solution sentences, feature links, product screenshots) are written with `skills/product-plug.md`. Its placement, capability, plan, and no-click-path rules apply.
- Every H2 opens with a direct 1–2 sentence answer. FAQ answers are 2–3 sentences with the answer first.
- Reddit scenarios are paraphrased or briefly quoted, and link to their thread. Never name the username. Every Reddit mention is followed by a SCREENSHOT placeholder with the thread URL.
- Italic `Entities:` lines and writer-direction text from the brief never appear in the draft.
- Closing section comes right before the FAQs (FAQs are always last) and is never titled "Conclusion". It ends with the brand + solution sentence carrying a single CTA to the brief's CTA URL.
- Repeated blocks: follow the brief's labels exactly if given (including ones added by hand). If the brief has none, don't create one: write normal prose and suggest it in the QA notes. Bold lead-ins, never headings. Answer first, specific detail under every label, never withhold information.
- No em dashes, no emojis, no banned filler phrases. American English.
- Match each section's format to its question type (see the table in Step 4).
- "Google confirms" only with a link to Google's own documentation. Third-party findings are "studies suggest" with a source. Unconfirmed practice is "many SEOs believe", never fact.
- A subtopic that has its own internal link page gets 1–2 sentences woven into existing copy plus the link, unless the brief's direction asks for depth.
- Explicit dates, never relative time words.
- Outside listicles and comparisons, no competitor names unless in the brief's entities. Never disparage, never link competitor domains (except flagged studies).
- Funnel stage language: Top / Middle / Bottom — never ToFu / MoFu / BoFu.
- Output format: create a Google Doc in the drafts folder (Step 6), titled with the H1 only, with the metadata block, keyword block (Seed, Primary, and Secondary KWs, the Secondary KWs on one line separated by commas), draft, and Writer QA notes. Placeholders are highlighted `#f1fa8c`. If Drive is unavailable, fall back to inline markdown in chat. Do not create a local .md file.
- Placeholders always use `[TODO · TYPE: …]`.
- No links in the intro. Every link anchor is at least 3 words.
- No heading repeats the H1. Key Takeaways heading: "Key Takeaways: [H1 paraphrase with Primary KW]". FAQs heading: "FAQs About [KW]".

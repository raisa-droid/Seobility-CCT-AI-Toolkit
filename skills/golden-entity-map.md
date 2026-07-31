---
name: golden-entity-map
owner: ane@saas.group
last_updated: 2026-07-31
called_by: .claude/commands/brief.md — Step 1c
description: Generates a "Golden Entity Map" — the strict JSON entity/topic blueprint that AI search agents (Claude, Gemini, ChatGPT, Perplexity) and traditional search engines expect on a page for it to be treated as a top-tier, citable authority on a given topic. Called inline by brief.md at Step 1c — output is strict JSON parsed internally by the brief skill; it is never surfaced raw to the user. Use this skill whenever the user asks for AIO (Agentic/AI Optimization) or GEO (Generative Engine Optimization) entity planning, topical authority mapping, a "golden entity map," "entity coverage map," "citability blueprint," or wants to know what entities/concepts a page needs to rank or be cited for a topic. Works for ANY topic and ANY website/brand the user names — always ask for the target topic/page title and the target website/brand if either is missing, rather than assuming a previously discussed one. Trigger even if the user doesn't say "entity map" explicitly but describes wanting a list of must-have concepts, novel/differentiating angles, and things to avoid for a page to be seen as authoritative by AI systems.
---
 
# Golden Entity Map
 
Produces a strict JSON blueprint of the entities, concepts, and relationships a page needs — and needs to avoid — to be recognized by AI search agents and answer engines as a top-tier, citable authority on a given topic.
 
## When to use this
 
Trigger this skill for requests like:
- "Build a golden entity map for [topic] on [website]"
- "What entities does my page need to rank/be cited for [topic]?"
- "AIO/GEO entity plan for [brand]"
- "What should Claude/Gemini/ChatGPT expect to see on a page about [topic]?"
- Any request for a topical authority / entity coverage blueprint, even if phrased loosely (e.g., "help me figure out what concepts I'm missing for this page to be seen as authoritative")
This skill is **topic- and brand-agnostic**. Never hardcode a specific product, brand, or vertical into the output — always derive entities fresh from the topic and site context the user provides.
 
## Step 1: Gather required inputs
 
Before generating anything, make sure you have:
 
1. **Target topic / page title** — the exact subject or working title of the page (e.g., "How web teams can deploy more efficiently", "Best practices for B2B email deliverability").
2. **Target website / brand** — whose page this is for. This shapes tone, product-adjacent entities, and which "must_avoid" items would cause off-topic drift for that specific brand.
3. *(Optional but useful if offered)* Target audience/persona, competitor URLs, or existing page content to build on rather than start from scratch.
If either (1) or (2) is missing or ambiguous, ask a single clarifying question before proceeding — don't assume a topic or brand from earlier context unless the user clearly means "same as before." If the user provides a URL instead of a written topic, treat fetching/reading that page as part of gathering context (use web_fetch if available) rather than guessing its subject.
 
## Step 2: Research the entity landscape
 
Before writing the JSON, build a real picture of the topic — don't rely purely on memorized associations:
 
- Use web_search (a few targeted queries) to see what currently ranks and what AI Overviews / answer engines currently surface for the topic, so `must_include` reflects the real current landscape rather than a stale mental model.
- If the user supplied a URL or existing draft, fetch/read it to see what's already covered — this sharpens `novel_information_gain` (what's missing that competitors also lack) and avoids recommending entities already well-covered elsewhere.
- Identify the topic's natural scope boundary: what's core, what's adjacent-but-relevant, and what's a different vertical entirely (this last category feeds `must_avoid`).
## Step 3: Generate the JSON
 
Output **strictly valid JSON only** — no markdown code fences, no preamble, no trailing commentary — with exactly these three top-level arrays:
 
### `must_include`
10–15 critical technical/topical entities, concepts, protocols, or named practices central to the topic. Each item:
```json
{
  "entity": "string — the concept/entity name",
  "semantic_weight": "integer 1-10 — how central this is to establishing topical authority",
  "context": "string — one sentence on how/where this should appear on the page for correct framing"
}
```
Order roughly by descending semantic_weight. Weight 9–10 = foundational/definitional to the topic; 6–8 = strongly expected supporting concepts. Don't pad with filler entities just to hit 15 — use 6+ in practice and stop when coverage is genuinely complete.
 
### `novel_information_gain`
3–5 advanced, cutting-edge, or hyper-specific entities/relationships that most generic pages on this topic will NOT already cover. These are the differentiators that give the page "information gain" over the existing search/AI-answer landscape. Each item:
```json
{
  "entity": "string",
  "context": "string — why this is non-obvious and what specific angle/relationship to cover"
}
```
These should come out of Step 2's research — genuinely check what's missing from current top-ranking/cited content, not just generate plausible-sounding jargon.
 
### `must_avoid`
5–8 generic, outdated, or off-topic concepts that would dilute topical authority or cause semantic drift if included. Each item:
```json
{
  "entity": "string",
  "reason": "string — why including this would hurt topical authority or signal low sophistication"
}
```
Tailor at least 2–3 of these to the specific brand/website's vertical (i.e., adjacent domains this particular site should NOT drift into), not just generic "beginner content" filler.
 
## Step 4: Output rules
 
- Return **only** the JSON object — starting with `{` and ending with `}`. No ```json fences, no "Here's your entity map" preamble, no notes after.
- Use double-quoted keys/strings, valid JSON syntax, no trailing commas.
- Keep entity/context/reason strings concise (roughly one sentence each) — this is a machine-consumable blueprint, not prose.
- If the user asks for a different array count than the defaults above (e.g., "just give me 5 must_includes"), honor their explicit count instead of the 10–15/3–5/5–8 defaults.
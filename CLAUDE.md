# Seobility CCT AI Toolkit

## What this is
AI-powered content workflow toolkit for Seobility's English-language blog and landing pages. Built and maintained by Raisa (raisa@saas.group). Used by Jules (Seobility content manager) and the Content Creation Team (CCT).

## How to run the commands
Commands are slash commands in Claude Code. Available commands:

| Command | Invocation | File |
|---|---|---|
| Sera URL | `/sera-url [URL]` | `.claude/commands/sera-url.md` |
| Sera Keyword | `/sera-kw` or `/sera-keyword` followed by `primary kw: [...] seed kw: [...]` | `.claude/commands/sera-keyword.md` |
| Brief | `/brief [paste brief feed]` | `.claude/commands/brief.md` |
| Write | `/write [paste brief]` | `.claude/commands/write.md` |
| Refresh Analyze (draft) | `/refresh-analyze [blog URL] primary kw: … secondary kw: … contextual kw: …` | `.claude/commands/refresh-analyze.md` |
| Refresh Fix (draft) | `/refresh-fix [approval page link]` | `.claude/commands/refresh-fix.md` |

**Workflow:** Sera commands run first and output a brief feed block. Copy the brief feed block and run `/brief` to generate the full content brief. Copy the brief output and run `/write` to draft the blog post from it.

**Refresh (standalone, for published posts):** `/refresh-analyze` compares a published blog post against the top organic and AI-cited pages, checks facts and links, and publishes the findings on a private approval page (a claude.ai artifact) where you click Yes/No. `/refresh-fix` then applies the approved fixes and creates a `Fix_[H1]` Google Doc. Both run on the same machine (they share `.refresh-cache/`). **Setup: `docs/refresh-setup.md`.** Design: `docs/refresh-design.md`.

## Product context
All Seobility product, feature, pricing, and brand files are in `product-context/`. The Brief command loads these automatically when looking up product URLs and ICP data. Both Sera commands also check `seobility_features.md` at their writability/product-capability step (Step 4b in `/sera-url`, Step 4c in `/sera-kw`) before finalizing any Middle/Bottom suggestion — Middle and Bottom suggestions are product-proximate by definition and must not imply a capability Seobility doesn't have. Files:
- `seobility_features.md` — full feature list and descriptions
- `seobility_pricing.md` — pricing plans and limits
- `seobility_use_cases.md` — ICP and use case pages
- `seobility_homepage.md` — homepage messaging
- `Seobility_brand_summary.md` — brand positioning
- `Seobility_tone_of_voice.md` — tone and writing style

## Skills
Reasoning skills that commands execute inline — no external calls. Located in `skills/`:
- `product-plug.md` — writes every Seobility product mention in a draft (used by `/refresh-fix` when a fix needs a product mention)
- `golden-entity-map.md` — generates a Golden Entity Map (must_include, novel_information_gain, must_avoid arrays as JSON). Called by `/brief` at Step 1c.

## API scripts
Bash scripts in `scripts/` handle all external API calls. Commands call these via bash — do not call any n8n webhooks directly.

| Script | Purpose | Called by | Usage |
|---|---|---|---|
| `sera_dataforseo.sh` | Keyword suggestions + scoring | `/sera-url` (Steps 4c, 4c-ii), `/sera-kw` (Step 4c-ii) | `./scripts/sera_dataforseo.sh "seed kw"` |
| `brief_dataforseo.sh` | Keyword overview (SV + intent) | `/brief` (Step 1f) | `./scripts/brief_dataforseo.sh "kw1" "kw2" "kw3"` |
| `brief_dataforseo_paa.sh` | PAA questions fetch | `/brief` (Step 1a) | `./scripts/brief_dataforseo_paa.sh "H1 title"` |
| `brief_gemini.sh` | Gemini research synthesis | `/brief` (Step 1b) | `./scripts/brief_gemini.sh "H1 title"` |
| `brief_reddit_miner.sh` | Reddit thread mining | `/brief` (Step 1e) | `./scripts/brief_reddit_miner.sh "H1 title"` |
| `refresh_crawl.py` | Crawls a blog post into a snapshot with block IDs; `--compare` diffs it against the live page (no API call) | `/refresh-analyze` (Step 3), `/refresh-fix` (Step 2) | `python3 scripts/refresh_crawl.py URL [--compare]` |
| `refresh_serp.sh` | 7 SERP calls + stored-snapshot tiebreaker: organic top 3, AI Overview sources, PAA, tier | `/refresh-analyze` (Step 4) | `./scripts/refresh_serp.sh "primary kw" "URL"` |
| `refresh_aeo.sh` | 3 phrasings × 5 grounded Gemini runs, citations ranked | `/refresh-analyze` (Step 4) | `./scripts/refresh_aeo.sh "URL" "p1" "p2" "p3"` |
| `refresh_fetch.py` | Fetches and strips competitor pages (full text plus a short digest per page; DataForSEO content parsing as fallback) | `/refresh-analyze` (Step 5) | `python3 scripts/refresh_fetch.py --slug SLUG URL…` |
| `refresh_checks.py` | Mechanical SEO checks on the snapshot: H1 count, title/meta length, outdated years, close-variant keyword presence (H1, title, meta, intro, headings), stuffing, anchors under 3 words, product links, long paragraphs, FAQ questions vs body (no API call) | `/refresh-analyze` (Steps 3, 8) | `python3 scripts/refresh_checks.py SLUG --kw "primary kw" [--faq "q" …]` |
| `refresh_links.py` | Link status, redirects, soft 404s, dirty links (a post, `--urls`, or `--md` for links a draft adds) | `/refresh-analyze` (Step 3), `/refresh-fix` (Step 4) | `python3 scripts/refresh_links.py SLUG` |
| `refresh_sitemap.py` | Local copy of the Sitemap Cache; internal link candidates (all remaining blog posts plus a wiki shortlist) | `/refresh-analyze` (Steps 3, 8) | `python3 scripts/refresh_sitemap.py status \| ingest FILE \| query SLUG --terms "…"` |
| `refresh_decisions.py` | Resolves the approval-page decisions, checks the gate and the live page, prints the apply list | `/refresh-fix` (Step 1) | `python3 scripts/refresh_decisions.py --dir DIR` |
| `refresh_verify.py` | Fetches a source page itself and prints the real text around given terms or figures, or NOT FOUND (WebFetch only summarizes and can invent figures) | `/refresh-fix` (Step 2) | `python3 scripts/refresh_verify.py --url URL TERM… [--url URL2 TERM…]` |
| `refresh_facts.sh` | Grounded Gemini checks of third-party claims | `/refresh-analyze` (Step 8) | `./scripts/refresh_facts.sh "URL" claims.json` |
| `refresh_to_gdoc.py` | `write_to_gdoc.py` plus a green highlight for new copy (no API call) | `/refresh-fix` (Step 4) | `python3 scripts/refresh_to_gdoc.py doc.md doc.html` |
| `gdoc_upload.sh` | Creates a Google Doc from an HTML file through an n8n webhook (optional; `/refresh-fix` falls back to the Drive connector when it isn't configured) | `/refresh-fix` (Step 4) | `./scripts/gdoc_upload.sh "Title" file.html [folder_id]` |
| `refresh_cost.py` | Exact tokens and API-equivalent cost of past `/refresh` runs, from the saved chat transcripts (run it after a run) | you | `python3 scripts/refresh_cost.py [--last N]` |

Scripts require a `.env` file in the repo root with:
- `DATAFORSEO_LOGIN`
- `DATAFORSEO_PASSWORD`
- `GEMINI_API_KEY` (billing must be active: the refresher uses Gemini with Google Search grounding)
- `REFRESH_FOLDER_ID` (optional: Drive folder for the `/refresh-fix` Docs; empty = My Drive)

The refresh scripts also accept `DATAFORSEO_WEBHOOK_URL` / `GEMINI_WEBHOOK_URL` (n8n) instead of the keys; see `scripts/_api.sh`.

Copy `env.example` → `.env` and fill in credentials. Never commit `.env`.

## MCP connections required
These must be connected in your Claude Code session before running any command:

| MCP | Used for | Commands |
|---|---|---|
| Notion | Content Library cluster state check; metadata fetch; refresh keyword and funnel lookup | `/sera-url`, `/sera-kw`, `/refresh-analyze` |
| Google Drive | H1 cannibalization list; Sitemap Cache for internal links; refresh Fix Docs | `/sera-url`, `/sera-kw`, `/brief`, `/refresh-analyze`, `/refresh-fix` |

`/refresh-analyze` and `/refresh-fix` also need the `Artifact` and `ArtifactData` tools (Claude desktop app, Code tab) for the approval page.

**Notion Content Library:** `collection://344eba87-0b26-817b-980a-000b96d30f1d`
**H1 List (Google Drive):** file ID `1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc`, tab `gid=382952304` — Seobility published content only, cannibalization checks
**Sitemap Cache (Google Drive):** file ID `1dSPlYc_WD3HGp-kQgw6LVPBZksdAtu4LcBGbo6fQB1U` — internal link sourcing for `/brief` Step 2b

## Ownership
- **Raisa** — builds and maintains all commands, scripts, skills, and workflows
- **Jules** — owns and maintains `product-context/` files
- **CCT (Faith, Lize)** — users only

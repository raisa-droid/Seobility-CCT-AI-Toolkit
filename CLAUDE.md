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

**Workflow:** Sera commands run first and output a brief feed block. Copy the brief feed block and run `/brief` to generate the full content brief. Copy the brief output and run `/write` to draft the blog post from it.

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

Scripts require a `.env` file in the repo root with:
- `DATAFORSEO_LOGIN`
- `DATAFORSEO_PASSWORD`
- `GEMINI_API_KEY`

Copy `env.example` → `.env` and fill in credentials. Never commit `.env`.

## MCP connections required
These must be connected in your Claude Code session before running any command:

| MCP | Used for | Commands |
|---|---|---|
| Notion | Content Library cluster state check; metadata fetch | `/sera-url`, `/sera-kw` |
| Google Drive | H1 cannibalization list; Sitemap Cache for internal links | `/sera-url`, `/sera-kw`, `/brief` |

**Notion Content Library:** `collection://344eba87-0b26-817b-980a-000b96d30f1d`
**H1 List (Google Drive):** file ID `1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc`, tab `gid=382952304` — Seobility published content only, cannibalization checks
**Sitemap Cache (Google Drive):** file ID `1dSPlYc_WD3HGp-kQgw6LVPBZksdAtu4LcBGbo6fQB1U` — internal link sourcing for `/brief` Step 2b

## Ownership
- **Raisa** — builds and maintains all commands, scripts, skills, and workflows
- **Jules** — owns and maintains `product-context/` files
- **CCT (Faith, Lize)** — users only

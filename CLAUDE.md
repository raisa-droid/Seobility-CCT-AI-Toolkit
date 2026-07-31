# Seobility CCT AI Toolkit

## What this is
AI-powered content workflow toolkit for Seobility's English-language blog and landing pages. Built and maintained by Raisa (raisa@saas.group). Used by Jules (Seobility content manager) and the Content Creation Team (CCT).

## How to run the skills
Skills are run as slash commands in Claude Code. Available commands:
- `/sera-url [URL]` — content suggestions from a performing blog URL
- `/sera-keyword` — content suggestions from a known keyword gap
- `/brief` — full content brief from a brief feed

Commands are in `.claude/commands/`. Each command file contains the full skill logic.

## Product context
All Seobility product, feature, pricing, and brand files are in `product-context/`. Load the relevant files before running any skill. Files:
- `seobility_features.md` — full feature list and descriptions
- `seobility_pricing.md` — pricing plans and limits
- `seobility_use_cases.md` — ICP and use case pages
- `seobility_homepage.md` — homepage messaging
- `Seobility_brand_summary.md` — brand positioning
- `Seobility_tone_of_voice.md` — tone and writing style

## API scripts
Bash scripts in `scripts/` handle all external API calls. Claude Code calls these via bash tool — do not call the n8n webhooks directly.

| Script | Purpose | Usage |
|---|---|---|
| `sera_dataforseo.sh` | Keyword suggestions + scoring for Sera URL skill | `./scripts/sera_dataforseo.sh "seed kw"` |
| `brief_dataforseo.sh` | Keyword overview (SV + intent) for Brief skill | `./scripts/brief_dataforseo.sh "kw1" "kw2" "kw3"` |
| `brief_gemini.sh` | Gemini research for Brief skill | `./scripts/brief_gemini.sh "H1 title"` |

Scripts require a `.env` file in the repo root with:
- `DATAFORSEO_LOGIN`
- `DATAFORSEO_PASSWORD`
- `GEMINI_API_KEY`

Copy `env.example` → `.env` and fill in credentials. Never commit `.env`.

## Data sources
- **Notion Content Library** — `collection://344eba87-0b26-817b-980a-000b96d30f1d` — metadata fetch and cluster state checks
- **H1 List (Google Drive)** — `1esAVjT_OACNuxU0hr2lTIDOTqZtIF_yduAau5c5TVlc` tab `gid=382952304` — Seobility-only cannibalization check
- **Sitemap Cache (Google Drive)** — `1dSPlYc_WD3HGp-kQgw6LVPBZksdAtu4LcBGbo6fQB1U` — internal link sourcing

Connect Notion and Google Drive MCP in your Claude Code session before running any skill.

## Ownership
- **Raisa** — builds and maintains all skills, scripts, and workflows
- **Jules** — owns and maintains `product-context/` files
- **CCT (Faith, Lize)** — users only

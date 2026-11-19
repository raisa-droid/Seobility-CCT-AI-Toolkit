# Content Refresher: setup for a new user

For `/refresh-analyze` and `/refresh-fix` (draft, version 1). The full flow runs end to end; the quality of the fixes is still being tuned.

## 1. Get the code

The commands are on the branch `draft/refresh-command`, not on `main`.

```bash
git clone https://github.com/raisa-droid/Seobility-CCT-AI-Toolkit.git
cd Seobility-CCT-AI-Toolkit
git checkout draft/refresh-command
```

(Already cloned? `git fetch && git checkout draft/refresh-command`.) Open this folder in the **Claude desktop app (Code tab)**. The approval page needs the `Artifact` and `ArtifactData` tools, which the desktop app has.

## 2. Check your `.env`

The refresher uses the same keys as `/brief` and `/sera`, so if those already run for you, your `.env` is nearly done. It needs:

```
DATAFORSEO_LOGIN=
DATAFORSEO_PASSWORD=
GEMINI_API_KEY=
REFRESH_FOLDER_ID=1CTthW4EQ9qMEMAh1_xbhyB8GVv3InORS
```

- `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`: your DataForSEO account. Used for the Google results, People Also Ask and reading competitor pages.
- `GEMINI_API_KEY`: your Gemini API key, **with billing active**. The AI-citation check and the third-party fact check use Gemini with Google Search grounding, so they fail if the key has no credits ("prepayment credits are depleted").
- `REFRESH_FOLDER_ID`: the Drive folder the Fix Docs are created in. It starts as Raisa's temporary shared folder (she shares it with you as Editor). When you take over, create your own folder in Google Drive, open it and copy the ID from the URL (`drive.google.com/drive/folders/<ID>`). Empty = your My Drive.

Don't set `GDRIVE_WEBHOOK_URL` / `GDRIVE_WEBHOOK_TOKEN`: that is Raisa's optional n8n upload. Without it, `/refresh-fix` creates the Doc through your own Google Drive connector. Use your own keys. Don't set `DATAFORSEO_WEBHOOK_URL` or `GEMINI_WEBHOOK_URL` (Raisa's n8n shortcuts): if they are set they win over your keys.

`.env` is git-ignored; never commit it.

## 3. Check your tools in Claude

| Connector | What you need |
|---|---|
| Notion | Access to the Seobility Content Library database (keyword and funnel lookup) |
| Google Drive | Read access to the Sitemap Cache sheet; edit access to the folder in `REFRESH_FOLDER_ID` |

Python 3 and `jq` are the only other requirements (`brew install jq` if missing).

## 4. Run it

1. `/refresh-analyze [blog URL] primary kw: … secondary kw: … contextual kw: …` (the URL must contain `/blog`). Confirm at each stop. It ends with a link to an **approval page**.
2. Open the approval page (signed in to claude.ai), click Yes/No on every Decide item, skip any Applied fix you don't want, add notes. The status bar shows when everything is answered.
3. `/refresh-fix [approval page link]`. It ends with a link to the Google Doc `Fix_[H1]`: clean edited copy, approval summary and change checklist.

You publish the approval page yourself, so you own it and can save decisions; no sharing is needed. To let someone else decide on your page, share it with **edit** access (view-only can't save decisions).

## 5. Things to know

- **Run both commands on the same computer, in the same folder.** `-fix` reads `.refresh-cache/` from the `-analyze` run. It isn't synced.
- The first run downloads a fresh copy of the Sitemap Cache from Drive (it refreshes when older than 7 days).
- A run costs roughly $3 (analyze) plus $2.50 (fix) in Claude usage at API prices, plus a few cents of DataForSEO and Gemini. Exact numbers for your last run: `python3 scripts/refresh_cost.py`.
- Fix quality is still being tuned. Read the Fix Doc before using anything from it; `[TODO · VERIFY: …]` items need a human check.
- Design and decisions: `docs/refresh-design.md`.

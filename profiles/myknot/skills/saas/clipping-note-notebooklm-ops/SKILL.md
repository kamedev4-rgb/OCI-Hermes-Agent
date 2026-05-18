---
name: clipping-note-notebooklm-ops
description: Clipping Note NotebookLM
description_full: Clipping Note NotebookLM support and operational checks for kame.dev4
---

# Clipping Note NotebookLM Ops

Use this when working on kame.dev4 Clipping Note NotebookLM integration, URL clipping failures, or NotebookLM settings.

## Project location

- Main path: `/home/ubuntu/saas/clipping-note`

## Intended NotebookLM behavior

1. URL/GitHub/YouTube sources should be submitted to NotebookLM before any local fetch.
2. CSV/file sources should prefer NotebookLM file ingestion.
3. RAG registration should happen only from NotebookLM output.
4. Gemini is fallback only.
5. If NotebookLM is unavailable/fails and fallback is used, mark as fallback summary only rather than RAG-ready.

## Existing implementation details from May 2026 session

- Added package: `notebooklm-py==0.4.0`
- Added/used env vars:
  - `NOTEBOOKLM_ENABLED`
  - `NOTEBOOKLM_COOKIES_PATH`
  - `NOTEBOOKLM_MOCK`
- Added/used API concepts:
  - `apps/api/app/notebooklm_adapter.py`
  - `notebooklm_sessions` table for temporary Notebook tracking and cleanup
  - `/api/settings/notebooklm` reports configuration status
- UI should show:
  - processing provider: NotebookLM / Gemini fallback / manual required
  - RAG status: yes/no
  - NotebookLM setting status

## Operational checks

From `/home/ubuntu/saas/clipping-note`:

```bash
docker compose ps
curl -sS http://localhost:<api-port>/health
curl -sS http://localhost:<api-port>/api/settings/notebooklm
```

If exact port is unknown, inspect compose/env first.

Check DB columns/tables if needed:

- `clippings.processing_provider`
- `clippings.rag_status`
- `notebooklm_sessions`

## Known pitfall: 403 on URL fallback fetch

A test URL from `hakari-corp.com` returned `403 Forbidden` when fetched with `User-Agent: ClippingNote/0.1`, while normal browser-like UA returned `200 OK`. If URL jobs fail with 403, verify the UA from inside the worker container before blaming the remote URL.

Preferred fix is still NotebookLM-first ingestion. Browser-like UA is only for fallback fetch.

## NotebookLM auth state

NotebookLM remains unconfigured until a valid NotebookLM login storage/cookie file is placed on the server and `.env` has `NOTEBOOKLM_ENABLED=true` plus `NOTEBOOKLM_COOKIES_PATH=<path>`.

Bitwarden item for the user's Google credentials is named `Google_ID` (type `login`), not `Google`. If it is not visible after folder/permission changes, run `bw sync` first.

Useful Bitwarden commands/context:

```bash
export BITWARDENCLI_APPDATA_DIR="/home/ubuntu/.config/Bitwarden CLI"
/usr/local/bin/bw sync
/usr/local/bin/bw list items --search Google
/usr/local/bin/bw unlock --passwordenv BW_PASSWORD --raw
```

Also available via helper if needed:

```python
sys.path.insert(0, "/home/ubuntu/.hermes/skills")
from common.secrets import get_secret
get_secret("Google_ID")
```

Attempting to automate Google login for NotebookLM with Playwright/Chromium/Firefox on the server failed because Google redirected to `accounts.google.com/.../signin/rejected` before password entry. A later retry with `agent-browser` also did not bypass this: after installing the missing profile-local Playwright Chromium (`cd /home/ubuntu/.hermes/hermes-agent && npx playwright install chromium`), `agent-browser open https://notebooklm.google.com/` reached the Google email screen, but entering the Bitwarden `Google_ID` username still redirected to `signin/rejected` before the password screen. Treat this as a Google trust/environment rejection, not a typing/GUI issue.

Current practical path:

1. User logs in to NotebookLM from a normal PC browser, or MyKNOT provides a temporary remote GUI and the user performs the Google login there.
2. Export/provide a Playwright-compatible `storage_state.json` / NotebookLM auth file from that trusted logged-in browser session.
3. Place it on the server, e.g. under the Clipping Note storage directory.
4. Set `.env`:

```env
NOTEBOOKLM_ENABLED=true
NOTEBOOKLM_COOKIES_PATH=/app/storage/notebooklm_storage_state.json
```

5. Restart API/worker and verify `/api/settings/notebooklm` returns `configured:true`.

Shared-note handoff records created for this work:

- `01KRA3QPSP3CF5GYETVAXA3137` — `NotebookLM認証: PC側で行う作業`
- `01KRA3QRAB3G795NVAD1X9FWZ0` — `Clipping Note NotebookLM連携: 次セッション引き継ぎ`

## Operational hardening learned from May 17, 2026

When making NotebookLM operational changes, check these paths explicitly:

- `notebooklm_cleanup` jobs must not update the parent clipping status. A cleanup job should only update `processing_jobs` and `notebooklm_sessions`; otherwise a completed clipping can be reverted to `processing`, `pending`, or `failed` after cleanup.
- PDF/CSV fallback after failed NotebookLM `add_file` should not call the generic `save_summary()` path, because that can try NotebookLM `add_text` again. Call the Gemini/local summarization fallback directly and save via `save_result_summary()` with metadata such as `fallback_after: notebooklm_file`, preserving non-RAG/fallback status.
- Image processing is not part of the current NotebookLM-first scope. Keep image on Gemini Vision/manual fallback unless the product policy explicitly changes; otherwise mock/NotebookLM image summaries can be incorrectly treated as RAG-ready NotebookLM output.
- Do not treat `NOTEBOOKLM_COOKIE` alone as configured unless code actually passes it to `notebooklm-py`. Current practical configured criteria are `NOTEBOOKLM_ENABLED=true` plus `NOTEBOOKLM_COOKIES_PATH`, or mock mode for local adapter-path tests.
- In `notebooklm_adapter._real_summarize()`, if a temporary notebook is created and source add/chat fails before the session is saved, immediately attempt `client.notebooks.delete(nb.id)` before re-raising to reduce orphan notebooks.
- `NOTEBOOKLM_MOCK=true` is only for adapter-path testing; mock output is shaped as provider `notebooklm`, so leaving it enabled in real operation would make fake NotebookLM output RAG-indexed.

Useful verification commands used for this hardening:

```bash
python3 -m compileall apps/api/app
cd apps/web && npm run build
cd /home/ubuntu/saas/clipping-note
docker compose build api worker web
docker compose up -d api worker web
docker compose exec -T api python - <<'PY'
import urllib.request
for path in ['/health','/api/settings/notebooklm']:
    print(path)
    print(urllib.request.urlopen('http://127.0.0.1:8000'+path, timeout=5).read().decode())
PY
docker compose exec -T -e NOTEBOOKLM_ENABLED=true -e NOTEBOOKLM_MOCK=true api python - <<'PY'
from app import notebooklm_adapter
r = notebooklm_adapter.summarize_text('疎通テスト', 'NotebookLM mock path test。', source_type='text')
print({'configured': notebooklm_adapter.status()['configured'], 'provider': r['provider'], 'has_external_id': bool(r.get('external_notebook_id'))})
PY
```

## Verification after changes

Run as applicable:

```bash
python3 -m compileall apps/api/app
npm run build
docker compose build api worker
docker compose up -d api worker web
```

Then verify:

- `/health` returns 200
- `/api/settings/notebooklm` returns expected configured status
- A mock NotebookLM test can produce `processing_provider=notebooklm`
- Fallback path marks `rag_status=fallback_summary_only`

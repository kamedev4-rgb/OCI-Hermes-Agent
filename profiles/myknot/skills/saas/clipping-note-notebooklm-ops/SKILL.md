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

Attempting to automate Google login for NotebookLM with Playwright/Chromium/Firefox on the server failed because Google redirected to `accounts.google.com/.../signin/rejected` before password entry. Current practical path:

1. User logs in to NotebookLM from a normal PC browser.
2. User exports/provides a Playwright-compatible `storage_state.json` / NotebookLM auth file.
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

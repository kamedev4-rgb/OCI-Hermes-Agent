---
name: clipping-note-design
description: "Clipping Note設計"
description_full: "Use when discussing, planning, designing, or implementing Clipping Note, the SaaS successor to the GAS-based CrystaNote. Captures the user's confirmed product direction, architecture decisions, AI processing policy, PostgreSQL/RAG requirements, and NotebookLM/notebooklm-py risk handling."
version: 1.0.0
author: MyKNOT
metadata:
  hermes:
    tags: [clipping-note, saas, postgres, rag, notebooklm, gemini, myknot, knowledge-db]
triggers:
  - "Clipping Note"
  - "CrystaNote SaaS"
  - "新聞記事の切り抜き"
  - "notebooklm-py"
  - "MyKNOT 共通知識DB"
---

# Clipping Note Design

## When to use

Use this skill whenever kame-dev asks about Clipping Note, the SaaS successor to the GAS-based CrystaNote, including requirements, architecture, database design, AI summarization, import/export, RAG, or MyKNOT integration.

## Product concept

Clipping Note is an internet-era “newspaper clipping notebook.”

Primary goals:

1. Save information from URLs, PDFs, videos, X/Twitter, images, and other internet sources.
2. Summarize and organize it so the user can read it later or recall it later.
3. Provide full-text search and RAG over saved clippings.
4. Act as a shared knowledge DB between kame-dev and MyKNOT.
5. Keep the app code-based and automated; MyKNOT should assist only where judgment or exceptional handling is needed.

## Confirmed product decisions

- App name: `Clipping Note`.
- Initial permission design is not required.
- Do not design in a way that blocks later permission/workspace/team support.
- Include future-ready fields such as `owner_id`, `workspace_id`, and `created_by` even if initially single-user.
- PostgreSQL is the primary database, with explicit data types wherever practical.
- Use async processing jobs for extraction, summarization, retry, RAG indexing, imports, and notifications.
- CSV import is needed for existing CrystaNote data migration. If it is one-time, MyKNOT-assisted direct import is acceptable.
- CSV export is desirable and should be included.
- Cost and quota limits are deferred; do not over-specify them early.
- Full-text search and RAG are required core features.
- Store regeneration history.
- Failed jobs should retry several times, then notify the user if still failed.
- Current organization decision: keep `source_type` as the only source/kind classification and remove the separate source-like `categories` concept. `categories` and `clippings.category_id` were removed from the MVP DB and UI because they duplicated `source_type`. Current active source types include `url` (記事), `text` (テキスト), and `github`; schema enum also has future/legacy values such as `pdf`, `youtube`, `x`, `csv`, and legacy `tool` (do not use `tool` for new data). GitHub/SaaS should not be lumped into a generic tool type; GitHub is a source type, while SaaS/tool-ness is better represented by tags or later provider-specific types. Tags remain a closed master list: no free-form or AI-created out-of-master tags; AI may only choose from the master, and unmatched items fall back to `未分類`. Tags must be atomic; do not use slash-combined labels like `バイオ / 医療` or `AI / 機械学習`—split them into separate tags (`バイオ`, `医療`, `AI`, `機械学習`). Initial tag groups are `領域・テクノロジー`, `金融・ビジネス`, `社会・生活`, `組織・人間`, `情報タイプ`, and `システム`. Implemented in the MVP via `apps/api/app/taxonomy.py`, `/api/taxonomy`, and system `tags` with `group_name`/`display_order`/`active`; `/api/taxonomy` may return `categories: []` only as temporary compatibility.

## PostgreSQL data model direction

Prefer separated tables instead of a spreadsheet-like wide table:

- `users` / `workspaces` only as future-ready minimal structures if needed.
- `clippings`: user-facing saved item.
- `sources`: original source URL/type/provider metadata.
- `attachments`: uploaded PDFs/images/files or object storage references.
- `summaries`: generated summaries, user-edited summaries, and versions.
- `tags`: normalized tag records.
- `clipping_tags`: many-to-many relation.
- `processing_jobs`: async job state, retries, errors, and notification status.
- `import_jobs` / `export_jobs`: CSV import/export tracking.
- `rag_documents` / `embeddings` or equivalent: chunks and vectors for RAG.

Use explicit types:

- IDs: `uuid`.
- Dates: `timestamptz`.
- Statuses: PostgreSQL enum or `text` with `CHECK` constraint.
- Unstructured provider metadata: `jsonb`.
- Long content and summaries: `text`.
- Embeddings: `vector` if using pgvector.

Separate AI-generated output from user-edited output. Keep model/provider/prompt/version/input metadata for reproducibility.

## What to remove or shrink from GAS CrystaNote

Do not carry over these as-is:

- GAS / Google Sheets / Drive as core architecture.
- Spreadsheet-like schema design.
- Detailed user-editable prompt settings as a main feature.
- Fixed category hierarchy as the main organization model.
- GAS-era InputUI/AppUI split.
- Gemini-only processing assumption.

Prefer:

- DB + object storage + async queue.
- Tags, collections, full-text search, and RAG over fixed categories.
- Simple SaaS navigation: register/import, list/search, detail, export, settings.

## AI processing policy

Do not make NotebookLM/notebooklm-py the only production AI backend.

Recommended roles:

### NotebookLM/notebooklm-py primary path

Prefer NotebookLM/notebooklm-py first for all supported Clipping Note sources, not only long PDFs, because the user's Gemini API quota is finite/free-tier. Gemini API should be fallback and minimal normalization/tagging support, not the default first path.

Confirmed decisions:

- All PDFs should try NotebookLM first.
- Non-PDF sources should also try NotebookLM first when source ingestion is technically possible.
- NotebookLM authentication should use Bitwarden-managed secrets; in this environment the confirmed Bitwarden item is named `Google_ID` (not `Google`). Run `bw sync` before concluding it is missing, because the item appeared after sync/folder movement.
- Temporary NotebookLM notebooks must always be deleted after processing, both on success and failure.
- NotebookLM failures should retry 2 times before final failure/fallback handling.
- RAG should store NotebookLM output only, not the full extracted PDF/text by default. Gemini fallback summaries may be saved but should be marked as not RAG-indexed.
- UI should expose only a small processing-method metadata label, not raw unofficial API details. Add an explicit searchable metadata/status field for items without RAG indexing rather than using normal user tags.
- Notify the user only after final failure; NotebookLM failure followed by successful fallback should not notify by default.

Use NotebookLM/notebooklm-py for:

- PDFs, including short and long PDFs.
- Long documents.
- URL/text sources where NotebookLM can accept the source directly.
- GitHub sources by downloading the repository README and attaching it as a file to NotebookLM, rather than relying on raw GitHub URL ingestion.
- Multi-source reading and synthesis.
- Human-readable review output.

Important risk note:

- `notebooklm-py` is unofficial and uses undocumented Google APIs.
- It can break without notice and has opaque rate/account limits.
- Do not make it an irreplaceable SaaS foundation; wrap it behind an adapter interface.
- If a temporary NotebookLM notebook is created, delete it after the job.
- Add cleanup jobs for deletion failures.

### Gemini API fallback / minimal support path

Use official LLM APIs such as Gemini API only as fallback or minimal normalization/tagging support when NotebookLM fails, is disabled, cannot ingest the source, times out, or returns unusable output. Because Gemini API quota is finite/free-tier for the user, avoid using it as the first-choice path.

Gemini remains useful for:

- JSON/structured output normalization when absolutely needed.
- Tagging/classification if NotebookLM output lacks structure.
- Short-source fallback summarization after NotebookLM failure.
- RAG answer generation if no better local/NotebookLM-backed answer path exists.

For long PDFs, Gemini fallback may also fail due to input limits/timeouts; in those cases final user notification and `manual_required` may be preferable to spending Gemini quota repeatedly.

### MyKNOT fallback

Use MyKNOT only for:

- X/Twitter or sources NotebookLM cannot handle.
- Retrieval failures or restricted pages.
- Ambiguous cases needing judgment.
- Exception recovery after automated routes fail.

Keep MyKNOT token usage low: do not send full raw corpora unless necessary; pass extracted snippets, metadata, and error context.

## RAG requirements

RAG is core, not optional.

Store enough data for retrieval:

- Clean extracted text.
- Chunks.
- Embeddings.
- Source references.
- Summary versions.
- Tags and timestamps.

MyKNOT should be able to query this DB as a shared knowledge base with the user. Design retrieval APIs/CLI endpoints with MyKNOT access in mind.

## Job and failure handling

For async jobs:

- Use states such as `queued`, `processing`, `completed`, `failed`, `retrying`, `cancelled`.
- Track retry count, max retries, last error, provider, and source type.
- Retry transient extraction/AI/provider failures several times.
- Notify the user after final failure.
- Keep enough logs to inspect what failed without storing excessive sensitive content.

## CSV migration/import/export

CSV import should include:

- Column mapping from GAS/Sheets CrystaNote.
- Type conversion and validation.
- Duplicate detection.
- Error row reporting.
- Import job history.

CSV export should include user-facing clipping data, summaries, tags, source URLs, created/updated timestamps, and status. Prefer stable headers for future re-import.

## Implementation notes from MVP build

The first runnable MVP was implemented as a separate app at:

```text
/home/ubuntu/saas/clipping-note
```

Do not mix it into `/home/ubuntu/saas/shared-notes` unless the user explicitly asks. `shared-notes` is a Markdown/SQLite human note app; Clipping Note is a Postgres/worker/source-ingestion/RAG subsystem, so keeping them separate avoids architecture collisions.

Current local/Tailnet ports intentionally avoid conflicts with existing services:

```text
Tailnet Web: http://100.115.79.36:3001
Tailnet API: http://100.115.79.36:8000
PostgreSQL: 127.0.0.1:5433 -> container 5432
Redis:      127.0.0.1:6380 -> container 6379
```

For Tailscale-only exposure, bind only Web/API to the live Tailscale IP and keep DB/Redis localhost-only in `docker-compose.yml`:

```yaml
api:
  ports:
    - "100.115.79.36:8000:8000"
web:
  command: sh -c "npm run build && npm run start"
  ports:
    - "100.115.79.36:3001:3000"
db:
  ports:
    - "127.0.0.1:5433:5432"
redis:
  ports:
    - "127.0.0.1:6380:6379"
```

Also set Tailnet URLs in `.env`:

```bash
PUBLIC_API_BASE_URL=http://100.115.79.36:8000
NEXT_PUBLIC_API_BASE_URL=http://100.115.79.36:8000
PUBLIC_WEB_BASE_URL=http://100.115.79.36:3001
```

Re-check the live Tailnet IP before reporting or hard-coding it:

```bash
tailscale ip -4
```

MVP implemented scope:

- Docker Compose: `db`, `redis`, `api`, `worker`, `web`.
- FastAPI API + background worker.
- PostgreSQL/pgvector schema initialized by `python -m app.init_db`.
- Next.js Web UI for register/list/detail/search.
- URL, text, and GitHub clipping registration (`github` is for GitHub URLs; do not use generic `tool` for new data).
- Detail editing for title, Markdown `summary_long`, and master-list tags. Do not reintroduce category selection.
- `processing_jobs` async flow.
- URL fetch + HTML extraction.
- Summary/tag/chunk persistence.
- Keyword search and simple RAG answer API.
- MyKNOT reference/search integration API.
- Gemini summarization when `GEMINI_API_KEY` exists, with local extractive fallback when missing or failing. Keep `GEMINI_MODEL_LIGHT` on a currently available model such as `gemini-2.5-flash`; deprecated `gemini-1.5-flash` can return 404 and silently fall back to English extractive summaries if errors are swallowed.
- Editing support exists on the detail screen for title, Japanese Markdown `summary_long`, and closed-master tags only. Category editing must not be reintroduced because categories were removed.
- Detail screen retry/job UX is implemented: `再要約` calls `POST /api/clippings/{id}/retry`, clears stale clipping errors server-side, shows `last_error_message`, a retry guidance panel for `failed`/`manual_required`, and displays recent `processing_jobs` history. `再タグ` remains disabled because tag-only regeneration does not yet have a dedicated API. Important retry pitfall: historical text clippings do not preserve the original raw text separately; retry payload reconstruction currently uses the current `summary_long`/`summary_short` as the available text source and preserves current master tags in the payload. If true raw-text regeneration is required later, add durable raw text storage before relying on retry for text items.
- Current lightweight Markdown renderer handles common Gemini output (`#`/`##`, bullets, numbered lists, bold, inline code, links, quote, hr). Next phase should replace it with a sanitized Markdown parser rather than continuing ad-hoc regex expansion.

UI iteration notes:

- The initial desktop-style MVP used one page with `register / list / detail` in columns. User asked for these to be paginated/separated. Preferred UI is page-navigation style with top nav and hash-based switching (`#register`, `#list`, `#detail`), list pagination, and card selection navigating to the detail page.
- After comparing with the user's GAS CrystaNote UI notes (`InputUI.html` and `AppUI.html` in shared-notes), the user explicitly felt the MVP had lost the old screen richness. Future Clipping Note UI work should preserve a GAS/CrystaNote-like rich dark UI rather than a plain admin panel.
- Visual direction from GAS CrystaNote:
  - dark background `#111827`, card background `#1f2937`, input background `#374151`, accent `#8bb72d` / `#6e9124`, Noto Sans JP;
  - top dark header with brand, total count, processing indicator, refresh; do not show NotebookLM links/buttons while the user says it is not currently used;
  - nav tabs like `記事一覧 / 新規登録 / 詳細要約 / 設定`;
  - registration screen as a centered card with a green gradient top strip, URL/text tabs, focus rings, loading/success affordances, and a strong `AI要約を開始` CTA;
  - list screen with search, tag filter, tag cloud, new registration button, RAG answer button, rich clipping cards, source/status badges, processing overlay, and pagination;
  - detail screen with a toolbar, tags, summary card, Markdown-like detailed summary, key points, job history, and disabled placeholders for unimplemented `再タグ`/`再要約`/`編集` actions.
- The current MVP API only supports URL/text. Keep image/PDF and other unavailable GAS-era actions visibly disabled or marked as next-phase rather than wiring fake behavior.
- Avoid relying on remote Material Symbols/Font Awesome rendering over Tailnet. In one iteration, Material Symbols appeared as literal strings such as `menu_book` and `chevron_right`; fix by either defining the full icon font CSS correctly or using local glyph/fallback icons (current approach uses `cn-icon` glyphs) and verify visually.
- Use Japanese labels. Keep `詳細要約` disabled until a clipping is selected.
- List page should show count range and pager, e.g. `2件中 1〜2件`, `前へ`, `1 / N`, `次へ`. Current rich-card page size is 9.
- For PC list image items, GAS AppUI did **not** show the image thumbnail inside the card. It rendered image entries like normal article cards, showing an image/content-type badge and an `画像コンテンツ` style source row, while actual image preview was reserved for the detail screen/lightbox. If SaaS list cards feel unnatural after adding thumbnails, prefer this GAS-like pattern over fixed-height thumbnail cards: list = scan/select, detail = view image. Fixed card heights with thumbnails can create awkward empty space in text cards and cramped image cards.
- On mobile, make the page nav fixed at the bottom so the primary screens are easy to switch.
- Latest user preference from UI iteration: keep the richer GAS/CrystaNote dark shell, but the detail page should use the older AppUI-style structure where the Markdown-like `詳細要約` is the main content. Avoid over-splitting detail into separate `短い要約 / 詳細要約 / 重要ポイント / 処理履歴` cards unless requested.
- Current detail layout preference: compact toolbar (`一覧に戻る`, disabled placeholders for `再タグ`/`再要約`/`編集`, `元記事` only for non-manual URLs), central detail card, source/status/date, title, tag chips, one primary `詳細要約` section rendered as Markdown, then compact metadata.
- Keep the top header small. The user explicitly disliked a large top header and excessive whitespace in detail view. Prefer a slim app header (~48px desktop), compact nav (~40px desktop), reduced detail padding, tighter Markdown heading/paragraph spacing, and no oversized blank areas.
- Do not use a persistent bottom/footer action bar for detail actions. UX decision: PC should integrate detail actions into the detail/header toolbar; smartphone should place a compact horizontally scrollable action row near the top/title area. Avoid “hide footer on scroll” patterns unless the user specifically requests them, because they are less predictable and can obscure reading space.
- Detail navigation UX preference: when entering detail from the list, switch to the detail screen immediately and show a centered loading state such as `詳細を読み込んでいます...` while `GET /api/clippings/{id}` runs. Do not leave the user on the list waiting silently. If detail fetch fails, show an error state with a way back to the list. Implementation pitfall found during review: fetch helpers that drive detail error UI must check `res.ok` before returning JSON; otherwise 404/500 JSON can be stored as `Detail` and render malformed UI. External source links opened with `target="_blank"` should include `rel="noreferrer"`.
- Current summary output preference: generate/store `title`, `summary_short`, and `summary_long` in Japanese. `summary_long` should follow the old GAS CrystaNote Markdown format confirmed from shared note `01KRHQ2SG3HBFJV0443QJ60NXC`: `## 概要`, `## 重要ポイント (箇条書き)`, `## 詳細`, and `## 結論`. Do not add `# AI詳細要約` or `## 確認したい観点` unless explicitly requested. `summary_short` remains a 2–3 sentence list-card excerpt. When Gemini is available, use it for Japanese title/summaries; local fallback should also emit this structure but cannot translate English source text.
- README/API仕様/フロント分割の第一段階は実施済み。`README.md` は現状構成・Tailnet/port・実装済み/部分実装・検証手順に追従し、`docs/api.md` に主要API・返却フィールド・job/attachment/taxonomy/NotebookLM/RAG/MyKNOT連携を整理済み。フロントはUI/UXを変えずに `apps/web/app/page.tsx` を薄くし、`apps/web/app/lib/types.ts`, `lib/api.ts`, `lib/format.ts`, `components/Icon.tsx`, `MarkdownView.tsx`, `RegisterPage.tsx`, `ListPage.tsx`, `DetailPage.tsx`, `SettingsPage.tsx` に第一段階分割済み。今後のフロント改修ではこの構成を前提に、状態管理刷新やUI再設計は別タスクとして扱う。
- NotebookLM is now the preferred first processing path for all supported sources. Gemini API is fallback/minimal support because the user's Gemini quota is finite/free-tier.
- For GitHub sources, download the repository README and attach it to NotebookLM as a file. Do not rely on GitHub URL ingestion for the primary path.
- RAG stores NotebookLM output only by default. Gemini fallback summaries may be saved as summaries but should not be indexed into RAG unless this policy changes.
- Markdown rendering, image support, and PDF support have been implemented. PDF implementation uses `source_type=pdf`, `POST /api/clippings/pdf` multipart upload, existing `attachments` storage under `/app/storage`, `pypdf==5.1.0` text extraction, async `summarize` worker handling via `save_pdf_summary`, Gemini Japanese summarization/tagging when extractable text exists, `manual_required` fallback for scanned/unextractable PDFs, RAG chunks for summary plus extracted text, list cards with `PDF` badge and filename/`PDFコンテンツ` source row, and detail-screen PDF link. Keep list cards thumbnail-free for PDF/image: list = scan/select, detail = view/open.
- X support is not currently implemented beyond the DB enum value. API `SourceType`, UI, and Worker handling do not support `x` yet. Initial recommended X approach is stable manual-assisted capture: `source_type=x`, X post URL in `sources.url`, pasted tweet/thread text as the summarization input, optional title/tags. Avoid relying on simple fetch/scraping first because X login/JS/rate limits make extraction unreliable; official API or external fetchers can be evaluated later.
- NotebookLM support has been implemented in `/home/ubuntu/saas/clipping-note` as an isolated adapter, not a core hard dependency path. Key files/changes:
  - `apps/api/app/notebooklm_adapter.py` wraps `notebooklm-py==0.4.0` and supports mock mode.
  - `apps/api/requirements.txt` includes `notebooklm-py==0.4.0`; after changing it, run `docker compose build api worker` so the running containers actually have the package.
  - `.env.example` documents `NOTEBOOKLM_ENABLED`, `NOTEBOOKLM_COOKIE`, `NOTEBOOKLM_COOKIES_PATH`, and `NOTEBOOKLM_MOCK`.
  - `GET /api/settings/notebooklm` reports whether NotebookLM is configured; UI shows only simple Japanese status, not unofficial-API internals.
  - DB now has `clippings.processing_provider`, `clippings.rag_status`, and `notebooklm_sessions` for temporary-notebook lifecycle/cleanup state.
  - `job_type` includes `notebooklm_cleanup`; worker cleanup should retry and mark `notebooklm_sessions.cleanup_status`.
  - `rag_status` values currently used include `indexed`, `not_indexed`, `notebooklm_failed`, and `fallback_summary_only`.
  - `summary_provider` includes `notebooklm`; `save_result_summary()` indexes RAG chunks only when provider is `notebooklm`.
  - For real use, provide a NotebookLM Playwright storage/cookie path via `NOTEBOOKLM_COOKIES_PATH` and set `NOTEBOOKLM_ENABLED=true`. Use `NOTEBOOKLM_MOCK=true` only for local adapter-path testing.
- NotebookLM implementation notes:
  - Use `NotebookLMClient.from_storage(path=NOTEBOOKLM_COOKIES_PATH)`.
  - The user explicitly expects NotebookLM-direct ingestion before local fetching. For `url`, `github`, and `youtube` fetch jobs, first call the NotebookLM adapter with the original URL (`client.sources.add_url`) and only fall back to local `fetch_url()`/README fetch if NotebookLM is unavailable or fails. Do not fetch locally first just to provide text to NotebookLM; that reintroduces 403/bot-block issues and violates the confirmed design.
  - Create a temporary notebook, add file/URL/text source with `wait=True`, ask a Japanese summary prompt, parse the answer into `summary_short`/`summary_long`/`key_points`, and return the real `external_notebook_id`.
  - Cleanup should be consistent: either delete inside the adapter and do not enqueue cleanup, or preferably store the real `external_notebook_id` in `notebooklm_sessions` and let `notebooklm_cleanup` delete it. Do not store fake `temp-{clipping_id}` IDs for real sessions, because cleanup cannot delete the actual notebook.
  - `notebooklm-py` supports `client.sources.add_url`, `add_text`, and `add_file`; YouTube URLs are handled through `add_url` by the library. Include `github` in the URL-direct set if the current policy is direct NotebookLM URL ingestion; only use README fetch as fallback or if direct GitHub URL ingestion proves unreliable.
  - For CSV, upload via `POST /api/clippings/csv`, store as an attachment, and try NotebookLM `add_file` before any bounded text-preview fallback.
  - For PDFs, store `page_count`, `extracted_chars`, `long_document`, and `recommended_provider` in `sources.metadata`; when NotebookLM is unavailable and the PDF is long or extraction fails, prefer `manual_required` with `rag_status='notebooklm_failed'` rather than spending Gemini quota.
  - Real enablement requires `NOTEBOOKLM_ENABLED=true` plus a valid NotebookLM/Google Playwright storage state file path in `NOTEBOOKLM_COOKIES_PATH`. The confirmed Bitwarden item for the Google account is `Google_ID`; run `bw sync` if it is not visible. Bitwarden login/password alone did not produce a usable NotebookLM `storage_state.json` in headless Playwright: Google redirected to `accounts.google.com/.../signin/rejected` before password entry for both Chromium and Firefox. Do not claim NotebookLM is active unless `/api/settings/notebooklm` returns `configured:true` and a real adapter call succeeds.
  - If a URL unexpectedly fails with 403 in local fallback, verify from both host and worker container with default UA and browser UA. `ClippingNote/0.1` was blocked by Cloudflare for `hakari-corp.com`, while browser-like headers returned 200; fallback fetch should use browser-like headers, but this is secondary to NotebookLM-direct ingestion.

Verification commands used:

```bash
cd /home/ubuntu/saas/clipping-note
python3 -m compileall apps/api/app
cd apps/web && npm install && npm run build
cd /home/ubuntu/saas/clipping-note
docker compose config
docker compose up -d db api worker web
curl -sS http://127.0.0.1:8000/health
curl -sS -X POST http://127.0.0.1:8000/api/clippings \
  -H 'content-type: application/json' \
  -d '{"source_type":"text","title":"MVP確認","text":"Clipping NoteのMVP確認です。URLとテキストを保存し、要約と検索ができます。","tags":["test"]}'
curl -sS --get --data-urlencode 'q=Clipping' http://127.0.0.1:8000/api/search
curl -sS -X POST http://127.0.0.1:8000/api/rag/query \
  -H 'content-type: application/json' \
  -d '{"query":"Clipping","top_k":3}'
```

Pitfalls learned:

- If `npm run build` fails with `.next` permission errors after Docker/root-owned builds, fix ownership or remove the build cache before retrying, e.g. `sudo chown -R ubuntu:ubuntu apps/web/.next` or `sudo rm -rf apps/web/.next`.
- Existing host services may already bind PostgreSQL `5432`, Redis `6379`, and shared-notes Web `3000`; use `5433`, `6380`, and `3001` for Clipping Note locally.
- For Tailnet access, do not publish Postgres/Redis to `0.0.0.0`; keep them bound to `127.0.0.1` and expose only Web/API on the Tailscale IP.
- Run the web service with `next build && next start` for Tailnet use. `next dev` displays the page, but can produce noisy/failed HMR WebSocket errors over Tailnet (`/_next/webpack-hmr`).
- When verifying Tailnet URLs from the host with `curl`, use `--noproxy '*'` if the environment has proxy settings; otherwise requests to raw `100.x.x.x` Tailnet IPs may hang or route incorrectly. If host-side Tailnet curl still hangs, verify API from inside the container instead, e.g. `docker compose exec -T api python - <<'PY' ... urllib.request.urlopen('http://127.0.0.1:8000/health') ... PY`, then use browser/Tailnet UI for end-to-end confirmation.
- When adding web dependencies, remember `web_node_modules` is a Docker named volume mounted at `/app/node_modules`. Host-side `npm install` and image build are not enough for the running `web` service; run `docker compose run --rm web npm install` or recreate the volume, then restart `web`.
- For image attachments, convert UUIDs to strings before putting them into JSON/JSONB payloads or metadata (`Jsonb({"attachment_id": str(id)})`); otherwise worker/API jobs fail with `Object of type UUID is not JSON serializable`.
- API and worker can run DB initialization concurrently. Protect schema initialization with a PostgreSQL advisory lock to avoid extension/type creation races such as `duplicate key value violates unique constraint "pg_extension_name_index"` for `vector`.
- Add `.dockerignore` files for web/api; otherwise Docker may send local `node_modules`/`.next` and make web image builds very slow.
- For quick MVP usefulness, implement text + URL first and explicitly defer PDF/YouTube/X/CSV/NotebookLM/Discord. This produces a verifiable vertical slice without blocking on provider-specific complexity.
- The Clipping Note API/Web are bound to the Tailscale IP, so host-side `curl http://127.0.0.1:8000` can fail with connection refused even when containers are healthy. Use the Tailnet API with `--noproxy '*'` or run verification from inside the API container with `docker compose exec -T api python ... http://127.0.0.1:8000/...`.
- `GET /api/attachments/{id}` serves files; `HEAD` currently returns 405, so verify attachment delivery with `GET` and check status/content-type/byte length rather than using `curl -I`.
- When implementing PDF support, avoid adding X in the same pass if the user says X design is incomplete. `schema.sql` may already have `source_type=pdf`, but `apps/api/app/models.py` `SourceType`, `main.py` endpoint, `service.py` creation/summary helpers, `worker.py` summarize branch, `requirements.txt`, and `apps/web/app/page.tsx`/`style.css` all need coordinated updates.

## Answering guidance

When discussing architecture, keep responses concise. Default recommendation:

> Clipping Note should use PostgreSQL + async jobs + full-text/RAG as the durable foundation. NotebookLM/notebooklm-py is useful for heavy reading workloads but should be an adapter, not the only production backend. Gemini or another official LLM API should remain for stable structured processing and RAG.

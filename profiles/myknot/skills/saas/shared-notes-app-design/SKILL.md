---
name: shared-notes-app-design
description: "Design and implementation conventions for kame-dev's Tailscale-hosted shared notes app: Obsidian-like UI for humans plus direct Markdown/SQLite access for MyKNOT."
version: 1.0.0
author: MyKNOT
metadata:
  hermes:
    tags: [shared-notes, notes, markdown, sqlite, tailscale, saas, myknot]
triggers:
  - "共有メモアプリ"
  - "shared-notes"
  - "Obsidian風"
  - "MyKNOTが読めるメモ"
  - "ノートアプリ"
  - "Markdownメモ"
---

# Shared Notes App Design

## When to use

Use this skill when designing or implementing kame-dev's shared notes app: a Tailscale-hosted, Dockerized, Obsidian-like note app that both kame-dev and MyKNOT can use.

## Core goal

Build a private Tailnet SaaS-style app where:

- Humans get a rich, responsive note UI.
- MyKNOT can directly read/search/edit a shared knowledge base.
- Data remains portable and not locked inside the app.

Initial hosting target:

```text
~/saas/shared-notes/
Tailscale-only access
Docker Compose
No app authentication
```

## Product concept

```text
Human-friendly rich notes UI + MyKNOT-readable/editable shared knowledge base
```

Primary user pattern:

- Smartphone: mostly writing/capturing notes.
- PC: mostly reviewing/searching/connecting notes.

## Key design decisions

1. **No AI-share on/off flag**
   - Because MyKNOT is expected to access the app's data directory directly.
   - Access control belongs to storage/operational boundaries, not per-note UI flags.

2. **No authentication in initial version**
   - The app is Tailnet-only.
   - Do not add login/password unless the user asks later.

3. **No backup in initial version**
   - Keep history/version snapshots, but no separate backup feature unless requested.

4. **Markdown remains the source of portability**
   - The note body should be saved as Markdown-compatible files.
   - SQLite is an index/metadata/search accelerator, not the sole source of content.

5. **Initial editor should be Markdown editor + preview**
   - TipTap/Lexical rich editing can be added later.
   - This is more stable and closer to Obsidian's Markdown-first model.

6. **MyKNOT should use CLI + skill, not necessarily an API**
   - Direct Markdown/SQLite access is simpler and more token-efficient.
   - Provide CLI scripts and record usage in a skill so MyKNOT can operate consistently.

## Storage layout

Recommended layout:

```text
~/saas/shared-notes/data/
  notes/
    {note_id}.md
  history/
    {note_id}/
      {timestamp}.md
  shared-notes.sqlite
```

Markdown file format:

```md
---
id: 01HX...
slug: my-note
title: My Note
tags:
  - idea
  - myknot
created_at: 2026-04-29T...
updated_at: 2026-04-29T...
---

Body text...
```

Important UI rule:

- Do **not** show frontmatter inside the body editor.
- Show/edit metadata through a separate metadata panel.

## Database design

SQLite is an index/metadata layer. Initial tables:

```text
notes
note_fts
tags
note_tags
note_links
note_history
app_settings
```

### notes

```sql
CREATE TABLE notes (
  id TEXT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  file_path TEXT NOT NULL,
  excerpt TEXT,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  pinned INTEGER NOT NULL DEFAULT 0,
  archived INTEGER NOT NULL DEFAULT 0
);
```

### tags

```sql
CREATE TABLE tags (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  created_at TEXT NOT NULL
);
```

### note_tags

```sql
CREATE TABLE note_tags (
  note_id TEXT NOT NULL,
  tag_id TEXT NOT NULL,
  PRIMARY KEY (note_id, tag_id)
);
```

### note_links

For `[[note]]` internal links, including unresolved/future links:

```sql
CREATE TABLE note_links (
  id TEXT PRIMARY KEY,
  from_note_id TEXT NOT NULL,
  to_note_id TEXT,
  target_slug TEXT NOT NULL,
  target_title TEXT,
  link_text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

### note_history

Snapshots are stored as Markdown files; the DB stores metadata:

```sql
CREATE TABLE note_history (
  id TEXT PRIMARY KEY,
  note_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  history_file_path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  change_summary TEXT,
  parent_history_id TEXT
);
```

Diff display can be generated on demand by comparing Markdown snapshots. Do not store diffs initially.

### note_fts

Use SQLite FTS5 for title/body/tag search. Exact schema may depend on implementation, but it should index title, body, and tags.

### app_settings

```sql
CREATE TABLE app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

## UI requirements

### Responsive behavior

PC:

- 3-pane layout:
  - Left: notes list/tags/search.
  - Center: note body/editor.
  - Right: preview/backlinks/metadata.

Smartphone:

- 1-column layout.
- Initial screen: recent notes + prominent new-note button.
- Bottom navigation should stay minimal:
  - メモ / 新規 / 情報
- Do not include separate 編集 or 検索 buttons in the bottom nav unless a clear need appears.
  - 検索 belongs at the top of the メモ list.
  - 情報/metadata view should include an explicit “← 編集に戻る” button.
- In メモ/list mode on mobile, hide editor, preview, and metadata panes entirely; show only the list/search capture surface.
- Large touch targets and writing-first flow.
- Large touch targets and writing-first flow.

### Metadata UI

Metadata should be visible in UI as fields, not raw frontmatter.

Suggested fields:

```text
ID
Slug
Title
Tags
Created at
Updated at
File path
Content hash
Version
```

Read-only but copyable:

```text
ID
File path
Content hash
Created at
Updated at
Version
```

Editable:

```text
Title
Slug
Tags
```

Slug changes should warn the user because `[[slug]]` links may be affected.

Tags UI:

- Keep tags lightweight and free-text for now; do not implement a tag master screen or tag dropdown unless the user asks again.
- Use touch-friendly chips.
- Clicking a tag should search/filter by that tag.

## Implementation pitfalls learned

- UI should default to Japanese labels for kame-dev. Keep technical metadata names understandable, but primary buttons/navigation should be Japanese (e.g. `新規メモ`, `検索`, `保存`, `削除`, `メタ情報`, `バックリンク`, `履歴 / 差分`).
- New-note creation must not use a fixed slug such as `untitled`/`新規メモ` without collision handling. Because `notes.slug` is UNIQUE, generate unique slugs by appending `-2`, `-3`, etc. before inserting.
- Slug is useful as a human-readable stable identifier for links and frontmatter, but should not be prominent in the normal writing flow. Hide slug editing under a `詳細設定`/advanced section in the metadata pane; keep title/tags/body as the primary visible fields.
- When storing DB `file_path`, make the path valid from both the Docker container and the host if CLI tools read files directly. A reliable pattern is mounting `./data` to `/home/ubuntu/saas/shared-notes/data` inside the container and setting `DATA_DIR` to that same absolute path.
- Verify creation from both API and browser UI; a successful build is not enough to catch runtime SQLite constraint errors.
- For Tailnet access, remember Tailscale IPv4 addresses are in the `100.x.x.x` range. For this host, `tailscale ip -4` previously returned `100.115.79.36`; re-check live before reporting if current access matters.

## Obsidian-like initial features

Implement in the MVP:

- Note create/edit/delete/list.
- Markdown editing and preview.
- `[[note]]` internal links.
- Tags.
- Checklists.
- Code blocks.
- Tables.
- Backlinks.
- Search with SQLite FTS.
- History snapshots and diff display.

Defer:

- Full graph view.
- MDX full support.
- Meilisearch.
- Postgres.
- Multi-user permissions.
- Public internet exposure.
- Realtime collaboration.
- Full TipTap/Lexical rich editor.

## MyKNOT CLI

Implemented app path:

```text
/home/ubuntu/saas/shared-notes/
```

Direct operation scripts:

```bash
cd /home/ubuntu/saas/shared-notes
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/create-note <title> [--tag tag] [--tags a,b] [--slug slug] [--body text]
# or: echo 'body' | DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/create-note <title> --tags a,b
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/search-notes <query>
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/read-note <id-or-slug>
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/append-note <id-or-slug> <text>
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/list-tags
```

They operate on:

```text
/home/ubuntu/saas/shared-notes/data/notes/*.md
/home/ubuntu/saas/shared-notes/data/shared-notes.sqlite
```

Use the CLI from future MyKNOT sessions rather than scanning every file manually when possible. The Docker compose service mounts `./data` to the same absolute path inside the container so DB `file_path` values are usable from both container and host.

## Implementation lessons from MVP iteration

- New blank notes must not reuse a fixed slug such as `untitled` or `新規メモ`; generate a unique slug automatically.
- Slug uniqueness checks must consider soft-deleted notes too, because the database has a global UNIQUE constraint on `notes.slug`.
- Slug is an advanced/internal identifier. Keep it out of the normal editor header; expose it only under metadata/details with explanatory copy.
- For phone UX, avoid showing the preview pane under the note list. List mode should show only the list/search UI.
- Prefer spreadsheet-like autosave for note edits:
  - body edits wait about 3 seconds before saving,
  - title/tags save on blur, not on the body autosave timer,
  - show state text like `未保存の変更あり` / `保存中…` / `保存済み`,
  - keep a manual `今すぐ保存` as a fallback,
  - preserve focused input and in-flight user edits when applying save responses.
- When changing mobile navigation, verify actual display states (`mobile-list`, `mobile-editor`, `mobile-tags`) rather than only desktop layout.
- Destructive actions should be visually lightweight but accessible: use a Google Fonts Material Symbols icon-only delete button (`delete`) placed at the right edge of the save/status row, while keeping `aria-label="削除"` and `title="削除"`.

## Current UI implementation conventions

- For new notes, do not use a fixed title/slug without uniqueness handling. `notes.slug` is UNIQUE, including rows that may be soft-deleted if the DB unique index is unconditional. Generate a unique slug against all existing rows, not only non-deleted rows.
- Keep `slug` out of the primary editing flow. Treat it as an advanced setting under metadata/details; normal users should see title, tags, body, and save state only.
- On smartphone, the bottom navigation should stay minimal: `メモ / 新規 / 情報`. Do not add separate `編集` or `検索` tabs unless there is a clear need. Search belongs at the top of the notes list; the info screen should include its own `← 編集に戻る` button.
- On smartphone list mode, hide editor/preview/metadata completely and show only the notes list. Avoid leftover preview panels below the list.
- Prefer spreadsheet-like autosave for note body editing. Body autosave should wait about 3 seconds after typing before saving, show visible states (`未保存の変更あり` → `保存中…` → `保存済み`), and keep a manual `今すぐ保存` button as a fallback. Title and tags should not be timer-autosaved; save them when the field loses focus (`blur`). When applying a save response in React, do not blindly replace the active note while the user may still be editing another field: track the latest active note in a ref, merge in any changes made while the save was in flight, and restore the focused input/selection. Otherwise background body autosave can steal focus from title/tag editing or overwrite in-progress edits.
- Destructive actions should be compact but clear: use Google Fonts Material Symbols for a trash icon (`delete`) with `aria-label="削除"`, placed at the right edge of the save/status row.
- For note-list deletion, use different interaction patterns by device: on mobile, left swipe should reveal a delete button rather than immediately deleting; on PC, show a compact delete action on hover/focus. Always keep a confirmation prompt before deleting. Mobile swipe actions must not be visible by default: keep move/delete panels `opacity:0` and `pointer-events:none` until the row has `swipe-move` or `swipe-delete`. The note row background should be transparent by default, with green/red backgrounds only in the corresponding swipe state. If the action panel looks clipped, increase both the action width and the matching card translate distance together, and ensure mobile z-index keeps the action above/beside the card. Note cards in a folder tree should not inherit folder indentation if the desired mobile layout is a centered/full-width card; avoid inline `marginLeft` on `.note-card` unless equal left/right compensation is also applied. Swipe actions need visual verification on mobile-sized layouts: the action pane must be wide enough to show icon + label, the card transform distance must match that width, and the action button must stay above the card (`z-index`) so it is not hidden as a thin red strip. Do not leave red swipe backgrounds visible in the normal/resting state; only show destructive red background while the row is actually swiped open.
- Note-list body previews should be readable but compact: strip common Markdown markers for display, preserve meaningful line breaks, use a subdued smaller font, and clamp to 5 lines with CSS (`-webkit-line-clamp: 5`).
- MyKNOT CRUD note operations are covered in the separate `shared-notes-crud` skill. Use `scripts/create-note` for new notes, `scripts/search-notes` + `scripts/read-note` for retrieval, `scripts/append-note` or direct Markdown edits for updates, and `scripts/delete-note` for soft-deletion. `scripts/search-notes` should quote/fallback FTS queries containing punctuation like hyphens.
- UI/API list search should also be punctuation-safe. Prefer a fallback chain of raw FTS5 `MATCH` → quoted phrase `MATCH` → escaped `LIKE` across title/excerpt/body/tags so search terms like `foo-bar` return an empty list or matches instead of a 500 error.
- Title, tags, and in-note search controls should be grouped under one collapsible section, not one disclosure per field. Use very small labels for field names and larger text for actual values.
- Metadata copy buttons should not rely only on `navigator.clipboard`, because Tailnet HTTP access may not be a secure context. Use `navigator.clipboard.writeText` when available, with a textarea + `document.execCommand('copy')` fallback.
- History restore should use the same persistence path as normal saves. The current implementation exposes `POST /api/notes/[id]/restore` with `{version, mode: 'overwrite'|'copy'}`; `overwrite` restores the selected snapshot into the current note, while `copy` creates a new note titled like `<original title> 復元 vN`. Both paths should call `saveNote()` so Markdown, SQLite metadata, FTS, tags, links, and snapshots stay synchronized. Destructive overwrite must require confirmation in the UI.
- History/diff UI should be modal-based. On mobile, the bottom nav is `メモ / 新規 / 情報` in note-list mode and `メモ / 新規 / 情報 / 差分` outside list mode; tapping `差分` opens a modal. Do not duplicate the diff button inside the editor's `編集項目` panel. The modal starts with a past-version list, selecting a version shows the diff, and the diff view includes `← バージョン一覧に戻る`, `現在のメモを上書き`, and `新しいメモとして復元`. PC may expose a right-pane `差分モーダルを開く` button that opens the same modal rather than duplicating inline controls.
- The Docker Compose service should run as the host `ubuntu` UID/GID (`1001:1001`) when writing `./data`, otherwise API/container-created history files can become root-owned and host-side CLI tools such as `scripts/delete-note` can fail with EACCES.
- Tag counts should exclude soft-deleted notes. `allTags()` should join `notes` with `deleted_at IS NULL` and hide zero-count tags so test/deleted tags do not linger in the UI.
- In-note search should search only the currently opened note body. Current preferred implementation:
  - show match count (`1 / N 件`),
  - support Enter and previous/next navigation,
  - do **not** programmatically select text in the Markdown textarea, because repeated Enter can accidentally overwrite/delete selected text,
  - use a mirrored editor overlay (`pre` behind the textarea) to color-highlight all matches and emphasize the current match,
  - scroll the textarea so the matched line is centered,
  - show the matched line in a highlighted preview/callout near the search control.
- Mermaid preview support is implemented for fenced code blocks using `mermaid` in the client component. Prefer a static client import (`import mermaid from 'mermaid'`) over dynamic `import('mermaid')` in this Next/Turbopack app, because dynamic chunk loading was observed to leave the preview unrendered in browser verification. Run Mermaid rendering after every render (or otherwise account for React re-renders resetting `dangerouslySetInnerHTML`) so rendered SVGs are not replaced by the original `<pre><code>`.
- Folder hierarchy is implemented as lightweight `folder_path` metadata plus a `folders` table for empty folders/CLI CRUD. `folder_path: ''` means the root folder and should be displayed as `ルート`, not `未分類`. PC and mobile note lists should both use an IDE-like tree. The root folder should be expanded by default on first render, while child folder rows should remain collapsed by default; tapping/clicking a folder toggles expand/collapse, and tapping/clicking again collapses it. The mobile note list must also expose folder create, move, and delete actions, including left-swipe on a folder row to reveal a delete button. The folder operation button should be labeled `移動`, not `変更`; tapping it should open a destination-folder picker/sheet and move the selected folder under the chosen parent folder instead of asking the user to type a path. Note movement should not rely on typing folder paths: on mobile, right swipe reveals `移動` and opens a folder picker, with long-press drag-and-drop as a faster direct manipulation path; on PC, drag note cards onto folder rows. Do not use emoji in the tree; Google Fonts Material Symbols (`folder`, `folder_open`, `description`, `create_new_folder`, etc.) are acceptable. Deleting a folder is allowed even with child folders/notes; it removes the folder classification and moves affected notes to root rather than deleting notes.
- For folder hierarchy support, prefer a single `folder_path` string on each note rather than a heavier folder table initially. Persist it in both SQLite (`notes.folder_path TEXT NOT NULL DEFAULT ''`) and Markdown frontmatter (`folder_path: Projects/shared-notes`) so the app stays portable and MyKNOT-readable. Treat empty `folder_path` as the root folder, not as “uncategorized”; in the UI show `ルート`, not `未分類`.
- The note list should represent folder hierarchy like an IDE-style tree. Do not use emoji in UI/design examples; Google Fonts Material Symbols are acceptable (e.g. `folder`, `description`, `expand_more`, `chevron_right`).
- Folder filtering and search should compose: selecting a folder narrows the note list, and text search should search within that selected folder when present. Creating a note while a folder is selected should create it in that folder unless the selected node is the global/all view.
- Folder edits must participate in the existing autosave race-protection logic. Add `folder_path` to `changedWhileSaving` comparisons and to the merged `nextActive` object so body autosave cannot overwrite an in-flight folder change.
- Folder support is not complete unless the CLI can operate on it. Add/maintain commands such as `scripts/list-folders [--json]`, `scripts/list-notes [--folder <path>] [--json]`, `scripts/move-note <id-or-slug> <folder-path|/>`, plus `--folder` on `scripts/create-note` and folder-aware `scripts/search-notes`. CLI changes must update both SQLite and Markdown frontmatter, not only one side.

## Completion criteria for the MVP

The first working version is complete when:

1. Docker container starts successfully.
2. The app opens over Tailscale.
3. Notes can be created, edited, saved, deleted, and listed.
4. Data survives container restart.
5. Markdown files are written with frontmatter.
6. SQLite index/search works.
7. `[[note]]`, tags, and backlinks are usable.
8. History snapshots exist and diffs can be displayed.
9. Smartphone writing flow is comfortable.
10. PC review/search flow is comfortable.
11. MyKNOT can use CLI scripts to create/search/read/append notes.

---
name: bmad-ux-gate
description: "UI/UXが絡む作業で、実装前にUX方針・画面構成・操作フロー・受け入れ条件を確定するゲート。"
description_full: "A lightweight BMAD UX Designer gate for MyKNOT. Use before implementation whenever UI/UX changes are involved. Produces ux-design.md or an equivalent concise design artifact."
version: 1.0.0
author: MyKNOT
metadata:
  hermes:
    tags: [bmad, ux, ui, design-gate, accessibility, mobile, myknot]
triggers:
  - "UI"
  - "UX"
  - "画面"
  - "モバイル"
  - "レスポンシブ"
  - "導線"
  - "操作フロー"
---

# BMAD UX Gate

## Purpose

Use this skill whenever a task affects user experience or UI. The goal is to decide the main UX before implementation, not to tune it ad hoc while coding.

## Mandatory rule

UI/UX is decided in the design phase. Do not proceed to implementation planning until the UX decisions and acceptance criteria are explicit enough to verify.

## When to use

Use for changes involving:

- Screen structure or layout
- Mobile input experience
- List/detail/search flows
- Tags, folders, delete, move, or other interaction patterns
- Information density and spacing
- Responsive behavior
- Accessibility
- Empty/error/destructive states
- Existing UI convention changes

Skip for purely backend changes with no user-facing behavior.

## Inputs to gather

Keep questions short. Prefer MyKNOT recommendation + closed question.

Required checks:

1. Target user
2. Primary action
3. First screen / initial state
4. Likely confusion points
5. Mobile vs PC differences
6. Information density and spacing
7. Operation count / friction
8. Empty states and failure states
9. Destructive action handling
10. Accessibility
11. Consistency with existing UI conventions

## Output artifact

Create or update:

```text
ux-design.md
```

If the project has a spec directory, place it under:

```text
docs/specs/<topic>/ux-design.md
```

If a full file would be excessive, include an equivalent concise UX section in the active spec/plan, but it must cover the same decisions.

## ux-design.md structure

```md
# UX Design: <topic>

## UX方針

## 対象ユーザーと主行動

## 画面構成

## 操作フロー

## モバイル仕様

## PC仕様

## コンポーネント方針

## 空状態・失敗時・破壊的操作

## アクセシビリティ

## 既存UI規約との整合

## 禁止事項

## 受け入れ条件
```

## Decision style

Use closed questions when confirmation is needed:

```text
私は「<推奨案>」で進めるのがよいと判断します。理由は<短い理由>です。この方針で確定してよいですか？
```

Do not ask open-ended design questions unless the missing information genuinely changes the design.

## Existing shared-notes conventions

When the target is shared-notes, preserve known conventions unless the user explicitly changes them:

- Japanese primary labels
- Phone write / PC review pattern
- Mobile bottom nav stays minimal: `メモ / 新規 / 情報`
- Search belongs in the note list, not as a bottom-nav tab
- Folder tree uses text / Material Symbols, not emoji
- Destructive actions require confirmation and should be visually compact but accessible
- Mobile list mode should not show editor/preview/metadata panes

## Claude Code use

Claude Code may review UX gaps or compare UX options, but only as thinking support. MyKNOT decides the final UX and writes the accepted design.

## Completion criteria

The UX gate is complete when:

- UX方針 is stated.
- Mobile and PC behavior are both specified when relevant.
- Destructive, empty, and failure states are covered.
- Acceptance criteria are testable.
- The implementation plan can refer to concrete UX decisions rather than guessing.

---
name: local-carshare-research
description: 近所のカーシェア調査
description_full: Research nearby Japanese carshare stations, verify official vehicle lists, and create a decision-ready shared note for kame-dev.
version: 1.0.0
author: MyKNOT
metadata:
  hermes:
    tags: [carshare, local-research, japan, shared-notes, mobility]
triggers:
  - "近所のカーシェア"
  - "カーシェアを調べて"
  - "車種と台数"
  - "タイムズカー"
  - "カーシェア候補一覧"
---

# Local Carshare Research

## When to use

Use when kame-dev asks to research nearby carshare options in Japan, especially around a specific address, and wants station lists, vehicle types, vehicle counts, practical recommendations, or a shared-notes writeup.

## Workflow

1. **Search from the exact address**
   - Yahoo検索 is often more useful than Google/Bing for Japanese local carshare results because it exposes Yahoo!マップ local listings with distance from the searched address.
   - Query examples:
     - `<住所> カーシェア タイムズ`
     - `<ステーション名> タイムズカー`
     - `"<ステーション名>" タイムズカー`

2. **Extract nearby station candidates from Yahoo results**
   - Capture:
     - station name
     - address
     - distance from the searched address when shown
     - official site link, usually `https://share.timescar.jp/view/station/detail.jsp?scd=...`
   - Use the Yahoo local list to discover stations that official area pages may omit or make hard to find.

3. **Verify each station on official detail pages**
   - Open each `share.timescar.jp/view/station/detail.jsp?scd=<code>` page.
   - Extract:
     - official station name
     - address
     - installed vehicles under `設置車両`
     - class if shown: ベーシック / ミドル / プレミアム
     - duplicate numbered vehicles such as `アクア（ハイブリッド）（1）`, `(2)` as separate vehicles/counts
     - warnings affecting usability, e.g. bicycle prohibited, one-way street, no stand sign
   - Official detail pages are the source of truth for vehicle names/counts; Yahoo snippets are useful but incomplete.

4. **Build a practical comparison**
   - Create tables for:
     - station list: priority, station, address, distance, vehicle count, vehicle types, evaluation
     - vehicle-by-use: family/shopping, cheap/fuel-efficient, kei, larger cars
     - use-case recommendations: weekly shopping, family leisure, driving practice, bulky shopping
     - total vehicle count by model/class
   - Flag uncertainty explicitly, e.g. if distance was not shown but official address/vehicle list was verified.
   - For kame-dev’s car decisions, emphasize reservation availability as the final unknown when not logged in.

5. **Shared-notes output**
   - Use the `shared-notes-crud` skill.
   - Create a separate note when the user asks for a list/material, rather than appending to an existing broad decision note, unless they explicitly request updating the existing note.
   - Good title pattern: `<住所/地域>近所のカーシェア候補一覧`.
   - Include confirmation time and source caveat: public pages can verify stations/vehicles, but real-time reservation status requires logged-in member page.

## Pitfalls

- Google and Bing may hit bot checks or show poor local detail; switch to Yahoo検索/Yahoo!マップ results.
- Times official area/category pages can be incomplete for the exact neighborhood; station detail pages from search results are more reliable.
- Do not infer vehicle count only from model names; count numbered duplicates and repeated `definition` lines.
- Do not claim reservation availability from public pages; only logged-in member pages show live reservation status.
- Distances in Yahoo results are approximate and query-dependent; label them as `目安`.

## Verification

- Read back the shared note with `scripts/read-note`.
- Search for a robust phrase such as a station name (`UR新豊里`) rather than punctuation-heavy address strings; Japanese FTS may miss address fragments.

---
name: delegate-to-cc
description: "Claude Code委譲"
description_full: "意図・背景・暗黙知の整理が必要なタスクをClaude Codeに委譲する。cc_available: trueのときのみ実行可能。"
version: 1.0.0
triggers:
  - Claude Codeに委譲
  - 要件定義してほしい
  - 設計してほしい
  - 整理してほしい
  - 分析してほしい
  - 調査してほしい
  - ドキュメント作成
  - 詳細設計
  - タスク分解
  - セッションを切って
  - 新しいタスク
---

# Claude Code委譲スキル

## このスキルを使う場面

cc_available: true のとき、意図・背景・暗黙知の整理が必要なタスクをClaude Codeに委譲する。
ジャンルは問わない（技術・調査・設計・ドキュメント・分析 すべて対象）。

## セッション管理ルール

- 1トピック = 1セッション
- セッション情報は `~/.hermes/cc_session.json` で管理する
- セッションIDが存在し timeout_at 以内なら継続、超過なら新規起動

## 手順

### Step 1: cc_available確認

```bash
python3 -c "
import json
with open('/home/ubuntu/.hermes/cc_status.json') as f:
    s = json.load(f)
available = s['weekly']['available'] and s['session']['available']
print('available' if available else 'blocked')
"
```

blocked の場合はkame-devに「現在Claude Codeへの委譲ができません（使用量制限中）。自分で処理するか、後ほど再試行してください。」と伝えて終了する。

注意: `cc_status.json` が available でも、Claude Code が未ログインだと `cc-session.py start/continue` が `Not logged in · Please run /login` を返すことがある。この場合は委譲を諦め、自分で処理する。ユーザーには必要なら「Claude Codeは未ログインで委譲できませんでした」とだけ短く伝える。

### Step 2: セッション確認

```bash
python3 /home/ubuntu/.hermes/scripts/cc-session.py check
```

出力:
- `new`: 新規セッションを起動する
- `continue <session_id>`: 既存セッションを継続する
- `timeout`: タイムアウト済み → 新規セッションを起動する

### Step 3: Claude Codeに委譲

**新規セッションの場合:**
```bash
python3 /home/ubuntu/.hermes/scripts/cc-session.py start "<topic>" "<prompt>"
```

**継続の場合:**
```bash
python3 /home/ubuntu/.hermes/scripts/cc-session.py continue "<prompt>"
```

`Not logged in · Please run /login` が返った場合は、委譲できていない。以後の作業を自分で続行するか、ユーザーに後で再試行可能な旨を伝える。

### Step 4: 完了処理

kame-devが「セッションを切って」と言った場合、または新しいタスクを明示した場合:
```bash
python3 /home/ubuntu/.hermes/scripts/cc-session.py close
```

### Step 5: 結果をkame-devに報告

Claude Codeからの返答をそのままkame-devに伝える。

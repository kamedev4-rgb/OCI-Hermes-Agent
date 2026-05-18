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

cc_available: true のとき、意図・背景・暗黙知の整理が必要な「考えるタスク」をClaude Codeに委譲する。
ジャンルは問わない（技術・調査・設計・ドキュメント・分析 すべて対象）。

**重要:** kame-devの運用方針では、Claude Codeには実装そのものを任せない。Claude Codeは思考補助ワーカーとして使い、MyKNOTが採否判断・実装指揮・最終責任を保持する。

委譲してよいタスク:

- 要件・背景・暗黙知の整理
- 仕様案・設計案の比較
- UI/UX設計案へのレビュー観点出し
- タスク分解や tasks.md の妥当性レビュー
- 実装前リスクの洗い出し
- バグ原因の仮説整理
- 実装後レビュー観点の作成

委譲しないタスク:

- コード編集
- テスト実行を含む実装完了作業
- git commit / push
- 本番反映、再起動、破壊的操作
- UI/UX最終決定
- kame-devへの承認判断代行

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

注意: MyKNOT profile では gateway 実行時の `HOME` は `/home/ubuntu/.hermes/profiles/myknot/home`。Claude Code 認証もこの profile home にコピー済みなので、通常は `claude -p ...` と `cc-session.py start/continue` と `delegate_task` 子エージェント内の `claude -p ...` はそのまま動く。`Not logged in · Please run /login` が返った場合は、まず `/home/ubuntu/.hermes/profiles/myknot/home/.claude/.credentials.json` と `/home/ubuntu/.hermes/profiles/myknot/home/.claude.json` の存在・権限(0600)を確認する。緊急回避だけ `CLAUDE_CODE_HOME=/home/ubuntu` または `HOME=/home/ubuntu` でグローバル認証を使う。関連Hermes commit: `7c45187 fix: use MyKNOT profile Claude Code auth`。

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

`Not logged in · Please run /login` が返った場合は、profile home 側の Claude Code 認証コピーを確認する。`cc-session.py` はデフォルトで現在の profile HOME を使い、必要時のみ `CLAUDE_CODE_HOME` で上書きできる。

### Step 4: 完了処理

kame-devが「セッションを切って」と言った場合、または新しいタスクを明示した場合:
```bash
python3 /home/ubuntu/.hermes/scripts/cc-session.py close
```

### Step 5: 結果を確認してkame-devに報告

Claude Codeの返答はそのまま転送しない。MyKNOTが内容を確認し、採用する点・採用しない点・次の判断を整理してからkame-devに報告する。

理由: Claude Codeは思考補助であり、採否判断・実装指揮・最終責任はMyKNOTが保持する。

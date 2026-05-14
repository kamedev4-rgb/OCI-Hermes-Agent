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

注意: `cc_status.json` が available でも、Claude Code が未ログインだと `cc-session.py start/continue` が `Not logged in · Please run /login` を返すことがある。MyKNOT profile では gateway 実行時の `HOME` が `/home/ubuntu/.hermes/profiles/myknot/home` になり、Claude Code の実認証が `/home/ubuntu/.claude` / `/home/ubuntu/.claude.json` にある場合、`claude` は未ログイン扱いになる。まず `HOME=/home/ubuntu claude -p 'Say OK only' --output-format text` で実認証側が動くか確認する。動く場合は Claude Code 自体ではなく、`cc-session.py` 実行時 HOME と認証ディレクトリの不一致が原因。恒久修正までは `HOME=/home/ubuntu HERMES_HOME=/home/ubuntu/.hermes/profiles/myknot python3 /home/ubuntu/.hermes/scripts/cc-session.py ...` で検証できる。ただし通常運用の修正は MyKNOT/Hermes の自己改修扱いなので、ユーザー承認後に行う。

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

`Not logged in · Please run /login` が返った場合は、まず `HOME=/home/ubuntu HERMES_HOME=/home/ubuntu/.hermes/profiles/myknot python3 /home/ubuntu/.hermes/scripts/cc-session.py ...` で再試行する。これで動くなら HOME/認証ディレクトリ不一致が原因。再試行も失敗した場合のみ、委譲できない旨をユーザーに短く伝える。

### Step 4: 完了処理

kame-devが「セッションを切って」と言った場合、または新しいタスクを明示した場合:
```bash
python3 /home/ubuntu/.hermes/scripts/cc-session.py close
```

### Step 5: 結果を確認してkame-devに報告

Claude Codeの返答はそのまま転送しない。MyKNOTが内容を確認し、採用する点・採用しない点・次の判断を整理してからkame-devに報告する。

理由: Claude Codeは思考補助であり、採否判断・実装指揮・最終責任はMyKNOTが保持する。

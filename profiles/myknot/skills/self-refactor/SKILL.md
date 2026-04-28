---
name: self-refactor
description: 自分自身（MyKNOT）のコード・設定を安全に修正するスキル（再起動前フェーズ）。
version: 1.1.0
author: MyKNOT
license: CC0-1.0
---

# self-refactor

自分自身（MyKNOT）のコード・設定を安全に修正するスキル（再起動前フェーズ）。
必ずこのフローを順番通りに守る。スキップ禁止。
再起動後の動作確認・報告は self-refactor-post スキルが担う。

## いつ使うか

- config.yaml・SOUL.md・スキルの SKILL.md を修正したいとき
- バグを自己修正するとき
- 新しいスキルを追加するとき
- hermes-agent/ のソースコードにパッチを当てるとき

---

## フロー（8ステップ・順番厳守）

### Step 1: git commit（修正前スナップショット）

```bash
cd ~/.hermes && git add -A && git commit -m "refactor: <目的>（修正前）"
```

変更がなくてもコミットを試みる（エラーは無視してよい）。

---

### Step 2: git pull（Claude Code や kame-dev の変更を取り込む）

```bash
cd ~/.hermes && git pull origin main
```

`git pull` が以下のように止まることがある:

- `fatal: Need to specify how to reconcile divergent branches.`

この場合は **勝手に merge / rebase / ff-only を選ばない**。作業を止めて kame-dev に報告し、どの pull 戦略で進めるか指示を仰ぐ。

**コンフリクトが出たら作業を止めて kame-dev に報告し、指示を仰ぐ。**

---

### Step 3: 変更対象ファイルを宣言する

修正を始める前に、変更するファイルを一覧にして Discord で kame-dev に提示する。
調査しながら変更範囲を広げない。

---

### Step 4: 現状調査

`~/.hermes/` のファイルを直接 bash で読む。

```bash
cat ~/.hermes/profiles/myknot/config.yaml
cat ~/.hermes/profiles/myknot/skills/<スキル名>/SKILL.md
```

---

### Step 5: 修正

対象ファイルのみ直接編集する。

**絶対に編集しないファイル（MyKNOT が常時書き込む）:**

| ファイル/ディレクトリ | 理由 |
|---|---|
| `state.db` | 会話状態・常時書き込み |
| `sessions/` | 会話ログ・常時書き込み |
| `cron/` | Cronジョブ実行状態・常時書き込み |
| `logs/` | ログ・常時書き込み |
| `gateway.pid` / `gateway_state.json` | プロセス管理 |
| `processes.json` / `.tick.lock` | 同上 |
| `channel_directory.json` / `discord_threads.json` | Discord状態 |
| `skill_index.db` / `.skills_prompt_snapshot.json` | スキルDBキャッシュ |

---

### Step 6: git commit + git push

```bash
cd ~/.hermes && git add -A && git commit -m "fix: <目的>（修正完了）" && git push origin main
```

---

### Step 7: BOOT.md に引き継ぎ指示を書く

再起動後のタスクを self-refactor-post スキルに引き継ぐため、
**再起動前に** BOOT.md に以下を書く。
`<目的>` の部分は今回の修正内容で置き換える。

```bash
cat > ~/.hermes/BOOT.md << 'EOF'
# 再起動後タスク（self-refactor-post）

self-refactor-post スキルを使って再起動後の動作確認と報告を行え。
修正内容: <目的>
EOF
```

---

### Step 8: 自分を再起動する

**この時点でセッションが終了する。** 続きは BOOT.md 経由で self-refactor-post が引き継ぐ。

```bash
systemctl --user restart hermes-gateway-myknot
```

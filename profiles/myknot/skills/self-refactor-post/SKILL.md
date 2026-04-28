# self-refactor-post

self-refactor スキルによる再起動後の動作確認・報告スキル。
BOOT.md から自動起動される。手動で呼び出すことも可能。
必ずこのフローを順番通りに守る。スキップ禁止。

## いつ使うか

- BOOT.md に「self-refactor-post スキルを使え」と書かれているとき（自動）
- self-refactor による再起動後に手動で動作確認したいとき

---

## フロー（3ステップ）

### Step 1: ログ確認

```bash
tail -30 ~/.hermes/profiles/myknot/logs/agent.log
```

---

### Step 2: Discord で kame-dev に報告する

**エラーなしの場合:**

send_message ツールで Discord の #talk チャンネルに送る。

```
再起動完了・正常動作を確認しました。
修正内容: <BOOT.md に記載された修正内容>
```

**エラーありの場合:**

エラー全文を Discord の #talk チャンネルで kame-dev に報告し、指示を仰ぐ。
**自己判断で再修正しない。**

---

### Step 3: BOOT.md を空にする

報告完了後、次回起動で BOOT.md が再実行されないよう空にする。

```bash
echo "" > ~/.hermes/BOOT.md
```

---

## ロールバック手順（エラー時に kame-dev から指示があった場合）

```bash
cd ~/.hermes
git log --oneline -5                                        # コミット履歴確認
git checkout <修正前ハッシュ> -- <ファイルパス>              # 特定ファイルを戻す
git add -A && git commit -m "revert: <目的>" && git push origin main
systemctl --user restart hermes-gateway-myknot
```

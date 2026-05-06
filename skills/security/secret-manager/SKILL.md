# secret-manager スキル

既存の Hermes スキルに Bitwarden 連携（secrets.py）を組み込む作業スキル。

## トリガー例

- 「xitter スキルに Bitwarden を連携して」
- 「github-auth のトークンを secrets.py から取得するようにして」
- 「〇〇スキルのシークレット管理を追加して」

## 処理フロー

1. 対象スキルのコード（.py / .sh）を読んで、シークレット取得箇所を特定
2. Bitwarden に対応アイテムが登録済みか確認
   - 未登録なら「〇〇をBitwardenに登録してください」と案内
3. `from common.secrets import get_secret` に置き換えてコードを修正
4. 動作確認（環境変数なしで実行できるか）
5. 結果を報告

## 組み込みパターン

### シェルスクリプト (.sh)

```bash
# 変更前
TOKEN="$DISCORD_TOKEN"

# 変更後
TOKEN=$(python3 -c "
import sys
sys.path.insert(0, '$HOME/.hermes/skills/common')
from secrets import get_secret
print(get_secret('Discord', field='password'))
")
```

### Python スクリプト (.py)

```python
# 変更前
token = os.environ["DISCORD_TOKEN"]

# 変更後
import sys
sys.path.insert(0, os.path.expanduser("~/.hermes/skills/common"))
from secrets import get_secret
token = get_secret("Discord", field="password")
```

## 注意事項

- Bitwarden アイテム名は運用ルール（Bitwarden運用ルール.md）に従う
- 変更前のコードは必ずバックアップを取ってから修正する
- 環境変数への依存を完全に取り除く（.env に残さない）

# account-lookup スキル

Bitwarden Password Manager に登録されたアカウント情報を検索・返答するスキル。

## トリガー例

- 「GitHub のパスワードは？」
- 「Twitter の ID を教えて」
- 「OpenAI の API キーを確認して」
- 「Discord のアカウント情報」

## 処理フロー

1. リクエストからサービス名とフィールド（username / password / notes / カスタム）を解釈
2. `get_secret(service_name, field=field)` で Bitwarden から取得
3. 値をマスクして Discord に返答

## マスクルール

| 値の長さ | マスク方法 | 例 |
|----------|-----------|-----|
| 8文字以下 | 後半をマスク | `abc*****` |
| 9〜20文字 | 先頭3文字と末尾3文字を残す | `abc***xyz` |
| 21文字以上 | 先頭4文字と末尾4文字を残す | `abcd****wxyz` |

## 内部利用（マスクなし）

他のスキルが `get_secret()` を直接呼ぶ場合は完全な値が返る。
このスキルは **人間（kame-dev）への返答専用**のマスク処理を行う。

## 実装

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.hermes/skills/common"))
from secrets import get_secret

def mask_value(value: str) -> str:
    n = len(value)
    if n <= 8:
        return value[:3] + "*" * (n - 3)
    elif n <= 20:
        return value[:3] + "***" + value[-3:]
    else:
        return value[:4] + "****" + value[-4:]

def lookup(service: str, field: str = "password") -> str:
    value = get_secret(service, field=field)
    if not value:
        return f"{service} の {field} が見つかりませんでした。"
    return f"{service} の {field}: `{mask_value(value)}`"
```

## 注意事項

- パスワード・トークン類は必ずマスクして返す
- サービス名が曖昧な場合は候補を列挙して確認する
- 「全部教えて」など範囲が広すぎるリクエストは拒否する

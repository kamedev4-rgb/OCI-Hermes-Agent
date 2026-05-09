---
name: slides
description: HTMLスライドをPDF化してDiscordに添付送信する
description_full: |
  ユーザーのリクエストを基にHTMLスライド（Reveal.js形式）を生成し、agent-browserでPDFに変換して
  Discordチャンネルにファイル添付として送信するスキル。
  プレゼン資料・説明資料・レポートスライドの作成依頼に使う。
  トリガー: スライド作って、プレゼン資料、deck、slides、発表資料、PDF添付
triggers:
  - スライド
  - スライドを作って
  - プレゼン資料
  - プレゼンを作って
  - 発表資料
  - deck
  - slides
  - スライドをPDFで
  - 資料を作って
---

# Slides スキル

HTMLスライドを生成 → PDF変換 → Discord添付の3ステップで完結する。

## ワークフロー

```
1. HTMLスライドを /tmp/slides_<topic>.html に生成
2. agent-browser でPDF変換 → /tmp/slides_<topic>.pdf
3. discord_send_file.py でDiscordに添付送信
4. 完了メッセージを返す
```

## ステップ1: HTMLスライド生成

以下のテンプレートをベースにスライドを生成する。ファイル名は `/tmp/slides_<topic>.html`（英数字・アンダースコアのみ）。

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TITLE_HERE</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/theme/black.css">
<style>
  .reveal { font-size: 28px; }
  .reveal h1 { font-size: 1.8em; }
  .reveal h2 { font-size: 1.3em; color: #42affa; }
  .reveal ul { text-align: left; margin-left: 1em; }
  .reveal li { margin: 0.4em 0; }
  .highlight { color: #42affa; font-weight: bold; }
  .reveal section { padding: 20px 40px; }
</style>
</head>
<body>
<div class="reveal">
  <div class="slides">
    <!-- スライド1: タイトル -->
    <section>
      <h1>タイトル</h1>
      <p style="color:#aaa;">サブタイトル</p>
    </section>
    <!-- スライド2以降 -->
    <section>
      <h2>見出し</h2>
      <ul>
        <li>ポイント1</li>
        <li>ポイント2</li>
      </ul>
    </section>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script>
<script>
  Reveal.initialize({
    width: 1280, height: 720,
    margin: 0.04,
    hash: false,
    transition: 'slide',
  });
</script>
</body>
</html>
```

## ステップ2: agent-browser でPDF変換

```bash
# HTMLを開いてReveal.jsが読み込まれるのを待ってからPDF化
agent-browser --allow-file-access open "file:///tmp/slides_<topic>.html" && \
agent-browser wait --load networkidle && \
agent-browser wait 3000 && \
agent-browser pdf "/tmp/slides_<topic>.pdf"
```

## ステップ3: DiscordにPDF添付送信

```bash
python3 ~/.hermes/skills/common/discord_send_file.py \
  "/tmp/slides_<topic>.pdf" \
  "スライド「<タイトル>」をお届けします 📊"
```

## 注意事項

- agent-browser の wait 3000 は Reveal.js の初期化待ち（CDN読み込みに時間がかかる）
- PDF変換後は `/tmp/slides_<topic>.html` と `/tmp/slides_<topic>.pdf` の両方が残る（自動削除しない）
- スライド枚数は10枚以内を推奨（agent-browser のタイムアウト回避）
- ネットワーク不通の環境では CDN が読み込めないため、インラインCSS版に切り替える

---
name: saas_builder
description: SaaSアプリ作成デプロイ
version: 1.0.1
author: kame-dev
description_full: kame-devとの対話を通じてWebアプリを開発し、OCI VM上のDockerコンテナとして起動する。アプリのコードを生成して ~/saas/<name>/ に配置し、コンテナを起動してアクセスURLを通知する。
metadata:
  hermes:
    tags: [saas, web, app, deploy, docker, development, アプリ開発]
triggers:
  - "アプリを作って"
  - "アプリを作りたい"
  - "ツールを作って"
  - "ツールを作りたい"
  - "作成して"
  - "作りたい"
  - "作って"
  - "デプロイして"
  - "デプロイしたい"
  - "saas"
  - "Webアプリ"
  - "ウェブアプリ"
  - "サービスを作"
  - "システムを作"
  - "アプリ開発"
  - "開発して"
---

# SaaS Builder

## 概要

kame-devとの対話を通じてWebアプリを開発し、OCI VM上のDockerコンテナとして公開するスキル。

`deploy.sh` がある環境ではそれを使い、無い環境では `docker compose` と `~/saas/manage.sh` / `ports.json` を使って直接ポート公開する。

## 手順

### Step 1: 要件ヒアリング

まず以下を確認する（一度に聞く、箇条書きで簡潔に）:
- 何を作るか: アプリの目的・主な機能
- 対象ユーザー: kame-devのみ / 外部公開
- 技術の希望: 特定の言語・フレームワークがあれば

返答が無い場合は、低リスクな自分用実用ツールとして進める。

### Step 2: 技術スタック選定

要件に応じてスタックを選ぶ:
- シンプルなUI + API: Python/FastAPI + HTML/JS
- リッチなUI: Node/Express + React または SvelteKit
- データ管理あり: SQLite（軽量）または PostgreSQL

選定理由を1行で説明して、必要なら確認を取る。

### Step 3: コード生成・配置

配置先:

```text
/home/ubuntu/saas/<app-name>/
├── docker-compose.yml
├── Dockerfile
├── src/
└── README.md
```

### Step 3.5: Git戦略

`~/saas/` 全体を1つのgit repoにはしない。各SaaSを独立したgit repoとして管理する。

コミットするもの:
- アプリのソースコード
- Dockerfile / docker-compose.yml
- package.json / requirements.txt など依存定義
- scripts / deploy補助スクリプト
- README / ROADMAP / 設計メモ
- 設定テンプレート (`.env.example` など)

コミットしないもの:
- 実行時データ (`data/**`)
- SQLite / DBファイル (`*.sqlite`, `*.db`, WAL/SHM含む)
- secrets / `.env` / 鍵ファイル
- `node_modules/`, `.venv/`, `__pycache__/`
- `.next/`, `dist/`, `build/`, `.cache/` など生成物
- logs / tmp

新規SaaSを作ったら `.gitignore` を作り、アプリディレクトリ内で `git init -b main` して初回コミットする。

### Step 4: Dockerコンテナ起動

注意: Hermes/MyKNOTのツール実行では `~` が `/home/ubuntu/.hermes/profiles/myknot/home` に解決される場合があるため、SaaS実体や管理ファイルには必ず `/home/ubuntu/saas` の絶対パスを使う。

ポート番号は原則 8100-8199 を使う。

```bash
cd /home/ubuntu/saas/<app-name>
if [ -x /home/ubuntu/saas/deploy.sh ]; then
  bash /home/ubuntu/saas/deploy.sh <app-name> <port>
else
  docker compose up -d --build
  [ -x /home/ubuntu/saas/manage.sh ] && bash /home/ubuntu/saas/manage.sh register <app-name> <port> /home/ubuntu/saas/<app-name>
fi
```

`deploy.sh` がある場合:
- docker-compose でビルド・起動
- Caddy設定を追加してリバースプロキシ設定
- URLを返す

`deploy.sh` が無い環境では Docker のポート公開でデプロイし、Caddy設定は権限がある場合だけ別途行う。sudo や Caddy admin API がブロックされたら再試行せず、直接ポートのURLを報告する。

### Step 5: 検証

- テストを実行して成功を確認する
- `docker ps` でコンテナ起動を確認する
- ブラウザまたはHTTPリクエストで `/health` と主要UI/APIを確認する

### Step 6: 結果通知

起動成功後、報告する:
- アクセスURL
- 主な機能の使い方（2-3行）
- Caddy未設定など制約があれば明記

## 注意事項

- `~/saas/` ディレクトリが存在しない場合は作成する
- リモートrepo化は依頼された場合だけ行う

---
name: docker-management
category: devops
description: Dockerコンテナ・イメージ・Composeを管理
description_full: |
  Dockerコンテナの起動・停止・再起動・削除・ログ確認・シェル接続などのライフサイクル管理を行う。
  イメージのビルド・pull・push・タグ付け・クリーンアップも担う。
  Docker Compose（マルチサービス構成）の起動・停止・状態確認・ログ追跡にも対応。
  ボリュームやネットワークの作成・削除・点検も行う。
  ディスク使用量の確認（docker system df）と不要リソースのクリーンアップ（prune）も実行する。
  クラッシュしたコンテナのデバッグ・ログ解析・Dockerfile最適化の提案も対応範囲。
  使うとき: コンテナを見たい・コンテナの状態を確認したい・Dockerを操作したい・ログを見たい・コンテナが落ちた・イメージをビルドしたい・Composeを動かしたい
requires_toolsets:
  - terminal
---

# Docker Management

Dockerコンテナ・イメージ・Compose スタックを標準 Docker CLI で管理する。

## いつ使うか

- コンテナの起動・停止・再起動・削除・状態確認
- ログ確認・シェル接続・プロセス確認
- イメージのビルド・pull・push・クリーンアップ
- Docker Compose（マルチサービス）の操作
- ボリューム・ネットワーク管理
- ディスク使用量確認・クリーンアップ
- クラッシュしたコンテナのデバッグ

## クイックリファレンス

| やること | コマンド |
|---------|---------|
| コンテナ一覧（稼働中） | `docker ps` |
| コンテナ一覧（全て） | `docker ps -a` |
| ログ確認（追跡） | `docker logs --tail 50 -f NAME` |
| シェル接続 | `docker exec -it NAME /bin/sh` |
| 停止 + 削除 | `docker stop NAME && docker rm NAME` |
| イメージビルド | `docker build -t TAG .` |
| Compose 起動 | `docker compose up -d` |
| Compose 停止 | `docker compose down` |
| ディスク使用量 | `docker system df` |
| 不要リソース削除 | `docker image prune && docker container prune` |

## 手順

### 1. コンテナ操作

```bash
docker ps -a                          # 全コンテナ確認
docker stop NAME                      # 停止（graceful）
docker start NAME                     # 起動
docker restart NAME                   # 再起動
docker rm -f NAME                     # 強制削除
docker logs --tail 100 -f NAME        # ログ追跡
docker exec -it NAME /bin/sh          # シェル接続
docker stats --no-stream              # リソース使用量
docker inspect NAME                   # 詳細情報（JSON）
```

### 2. イメージ操作

```bash
docker images                         # 一覧
docker build -t my-app:latest .       # ビルド
docker pull IMAGE                     # pull
docker rmi IMAGE                      # 削除
docker image prune                    # 未使用削除
```

### 3. Docker Compose

```bash
docker compose up -d                  # 全サービス起動
docker compose up -d --build          # 再ビルドして起動
docker compose down                   # 停止・削除
docker compose down -v                # ボリュームも削除（データ消失注意）
docker compose ps                     # サービス状態
docker compose logs -f SERVICE        # ログ追跡
docker compose exec SERVICE /bin/sh   # シェル接続
```

### 4. クリーンアップ

```bash
docker system df                      # 使用量確認（先に実行）
docker container prune                # 停止コンテナ削除
docker image prune                    # 未タグイメージ削除
docker volume prune                   # 未使用ボリューム削除
docker system prune -a                # 未使用イメージも含め全削除（要確認）
```

**注意:** `docker system prune -a --volumes` は名前付きボリュームも消える。データが消えるため必ず確認を取る。

## 確認手順

操作後は必ず結果を確認する：

- コンテナ起動確認 → `docker ps`（Status が "Up" か）
- ログ確認 → `docker logs --tail 20 NAME`
- ポート確認 → `docker port NAME` または `curl http://localhost:PORT`
- Compose 確認 → `docker compose ps`（全サービスが "running"/"healthy" か）
- ディスク確認 → `docker system df`（前後比較）

#!/bin/bash
# 使い方: deploy.sh <app-name> <port> <template: fastapi|express>

set -e

APP_NAME=$1
PORT=$2
TEMPLATE=${3:-fastapi}
APP_DIR=~/saas/$APP_NAME

if [ -z "$APP_NAME" ] || [ -z "$PORT" ]; then
  echo "Usage: deploy.sh <app-name> <port> [template: fastapi|express]"
  exit 1
fi

echo "=== デプロイ開始: $APP_NAME (port $PORT, template: $TEMPLATE) ==="

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR が存在しません。コードを先に配置してください。"
  exit 1
fi

TEMPLATE_DIR=~/.hermes/skills/saas_builder/templates/$TEMPLATE
cp $TEMPLATE_DIR/docker-compose.template.yml $APP_DIR/docker-compose.yml
sed -i "s/{{APP_NAME}}/$APP_NAME/g" $APP_DIR/docker-compose.yml
sed -i "s/{{PORT}}/$PORT/g" $APP_DIR/docker-compose.yml

if [ ! -f "$APP_DIR/Dockerfile" ]; then
  cp $TEMPLATE_DIR/Dockerfile $APP_DIR/Dockerfile
fi

docker stop saas-$APP_NAME 2>/dev/null && docker rm saas-$APP_NAME 2>/dev/null || true

cd $APP_DIR
docker compose build
docker compose up -d

echo "起動確認中..."
for i in $(seq 1 10); do
  if docker ps | grep -q "saas-$APP_NAME"; then
    echo "✅ 起動成功: saas-$APP_NAME"
    break
  fi
  sleep 3
done

~/saas/manage.sh register $APP_NAME $PORT $APP_DIR

echo ""
echo "=== デプロイ完了 ==="
echo "アプリ名: $APP_NAME"
echo "アクセス URL: http://100.115.79.36:$PORT"

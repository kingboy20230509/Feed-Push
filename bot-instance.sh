#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
action=${1:-}
name=${2:-}
if [[ ! "$name" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  echo '用法：bash bot-instance.sh {init|up|stop|restart|logs|status} <实例名>' >&2
  echo '实例名仅支持小写字母、数字、下划线和连字符，以字母或数字开头。' >&2
  exit 2
fi
instance="$repo/instances/$name"
case "$action" in
  init)
    umask 077
    mkdir -p "$instance/data"
    if [[ -e "$instance/.env" ]]; then
      echo "已有配置，未覆盖：$instance/.env"
      exit 0
    fi
    sed "s|^BOT_DATA_DIR=.*|BOT_DATA_DIR=./instances/$name/data|" \
      "$repo/.env.example" > "$instance/.env"
    echo "已创建独立实例，填写 Token 和管理员 ID：$instance/.env"
    exit 0
    ;;
  up|stop|restart|logs|status) ;;
  *) echo "不支持的操作：$action" >&2; exit 2 ;;
esac
if [[ ! -f "$instance/.env" ]]; then
  echo "请先执行：bash bot-instance.sh init $name" >&2
  exit 2
fi
compose=(docker compose --project-directory "$repo" --env-file "$instance/.env"
  -p "feed-push-$name" -f "$repo/docker-compose.yml")
case "$action" in
  up) "${compose[@]}" up -d --build ;;
  stop) "${compose[@]}" stop ;;
  restart) "${compose[@]}" up -d --force-recreate ;;
  logs) "${compose[@]}" logs --tail=100 -f ;;
  status) "${compose[@]}" ps ;;
esac

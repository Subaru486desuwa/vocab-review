#!/bin/bash
# 完整备份演示库（含账户哈希与学习记录）到被 Git 忽略的 backups/。在仓库根目录、docker compose 运行时执行。
set -euo pipefail
DIR=${1:-backups}
OUT="$DIR/vocab_review-$(date -u +%Y%m%dT%H%M%SZ).sql"
mkdir -p "$DIR"
docker compose exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot \
  --single-transaction --no-tablespaces --set-gtid-purged=OFF --default-character-set=utf8mb4 \
  --add-drop-table "$DB_NAME"' >"$OUT"
chmod 600 "$OUT"
echo "已备份：$OUT"

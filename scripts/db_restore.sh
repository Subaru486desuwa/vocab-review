#!/bin/bash
# 把 db_backup.sh 的备份恢复到指定库；库不存在时创建，同名表被替换。
# 用法：scripts/db_restore.sh <备份文件> <库名>。恢复到演示库会覆盖当前数据，先另行备份。
set -euo pipefail
FILE=${1:?备份文件}
TARGET=${2:?目标库名}
[[ $TARGET =~ ^[A-Za-z0-9_]+$ ]] || { echo "库名只允许字母、数字与下划线" >&2; exit 2; }
root() { docker compose exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 "$@"' mysql "$@"; }
root -e "CREATE DATABASE IF NOT EXISTS \`$TARGET\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
root "$TARGET" <"$FILE"
echo "已恢复到 $TARGET：$(root -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$TARGET'") 张表"

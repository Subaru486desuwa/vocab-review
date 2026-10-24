#!/bin/bash
# 导出全部表结构与内容表数据（词表、词条、词义、例句、题目与迁移记录），可导入空库。
# 不含账户、练习、作答、学习状态、模型登记与推理事件。在仓库根目录、docker compose 运行时执行。
set -euo pipefail
OUT=${1:-sql/export/vocab_review_content.sql}
CONTENT="schema_migrations wordbooks words word_senses wordbook_words examples questions"
# 以 root 在 db 容器内导出；密码经环境变量传入，不出现在命令行。
dump() { docker compose exec -T db sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysqldump -uroot \
  --single-transaction --no-tablespaces --skip-dump-date --set-gtid-purged=OFF --skip-add-locks \
  --default-character-set=utf8mb4 --order-by-primary $1 \"\$DB_NAME\" $2"; }
mkdir -p "$(dirname "$OUT")"
{
  echo "-- vocab-review 结构与内容表数据；由 scripts/db_export.sh 生成，内容为项目自编演示 v1。"
  echo "-- 导入空库后无需再执行 flask db upgrade（schema_migrations 已包含已执行版本）。"
  # 去掉 AUTO_INCREMENT 计数，避免泄漏用户与作答数量。
  dump "--no-data --skip-add-drop-table" "" | sed -E 's/ AUTO_INCREMENT=[0-9]+//'
  dump "--no-create-info --skip-extended-insert --complete-insert" "$CONTENT"
} >"$OUT"
echo "已导出：$OUT（$(grep -c '^INSERT' "$OUT") 行数据）"

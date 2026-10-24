#!/bin/bash
# S5 干净环境验收：把工作区中受 Git 管理的文件（不含 .env、artifacts/ 等被忽略内容）复制到临时目录，
# 用独立 compose 项目、全新数据卷与随机凭据，按 README 从零启动并逐项检查，最后删除项目与数据卷。
# 用法（仓库根目录）：scripts/handoff_check.sh [--keep]。端口 5001，不影响 5000 上的演示环境。
set -euo pipefail
SRC=$(pwd)
KEEP=${1:-}
PROJECT=vocab-review-handoff
PORT=5001
B=http://127.0.0.1:$PORT
WORK=$(mktemp -d)
J=$(mktemp)

cleanup() {
  if [ "$KEEP" != "--keep" ]; then
    (cd "$WORK" && docker compose down -v --remove-orphans >/dev/null 2>&1) || true
    rm -rf "$WORK"
  else
    echo "保留：$WORK（docker compose -p $PROJECT down -v 清理）"
  fi
  rm -f "$J"
}
trap cleanup EXIT

step() { echo; echo "## $*"; }
# 去掉 compose 的容器创建进度行；用 sed 保证过滤后为空时不改变退出码。
quiet() { sed -E '/^ ?(Container|Network|Volume|Image) /d'; }
dc() { docker compose "$@" 2>&1 | quiet; }
run() { docker compose run --rm -T web "$@" 2>&1 | quiet; }
sql() { docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" db mysql -u"$DB_USER" "$DB_NAME" -N -e "$1"; }
root() { docker compose exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -N "$@"' mysql "$@"; }
code() { curl -s -o /dev/null -w "%{http_code}" -b "$J" -c "$J" "$B$1"; }
expect() { local path=$1 want=$2 got; got=$(code "$path"); echo "GET $path → $got"; [ "$got" = "$want" ] || { echo "!! 期望 $want" >&2; exit 1; }; }
tok() { curl -s -b "$J" -c "$J" "$B$1" | grep -o 'name="csrf-token" content="[^"]*"' | head -1 | sed 's/.*content="//;s/"$//'; }
api() { local t; t=$(tok /dashboard); curl -s -w '\n%{http_code}' -b "$J" -c "$J" -X "$1" -H "X-CSRFToken: $t" -H 'Content-Type: application/json' ${3:+-d "$3"} "$B$2"; }
# 打印 HTTP 状态码与 data 中选定字段（或 error.code）；第二个参数为期望状态码。
show() { python3 -c 'import sys,json
raw=sys.stdin.read().rstrip("\n"); body,code=raw.rsplit("\n",1); d=json.loads(body)
print("HTTP", code, d["error"]["code"] if d["error"] else json.dumps({k:d["data"][k] for k in sys.argv[2].split(",") if k}, ensure_ascii=False))
sys.exit(0 if code==sys.argv[1] else 1)' "$@"; }
counts() {
  for t in $(root -e "SELECT table_name FROM information_schema.tables WHERE table_schema='$1' ORDER BY table_name"); do
    echo "$t $(root -e "SELECT COUNT(*) FROM \`$1\`.\`$t\`")"; done; }

echo "# executed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) commit=$(git rev-parse --short HEAD)$(git diff --quiet HEAD -- . ':!evidence/handoff' && echo '' || echo '+工作区改动') project=$PROJECT base=$B"

step "1. 复制受 Git 管理的文件到临时目录（等同干净克隆，不含 .env、artifacts/、data/raw/）"
git ls-files -z --cached --others --exclude-standard | while IFS= read -r -d '' f; do [ -e "$f" ] && printf '%s\0' "$f"; done \
  | tar --null -cf - -T - | tar -xf - -C "$WORK"
cd "$WORK"
echo "文件数 $(find . -type f | wc -l)；artifacts/：$(ls artifacts)；data/raw 存在：$([ -d data/raw ] && echo 是 || echo 否)"

step "2. 由 .env.example 生成随机凭据（不输出）"
python3 - "$PORT" "$PROJECT" <<'PY'
import os, secrets, sys
port, project = sys.argv[1:]
fill = {"SECRET_KEY": secrets.token_hex(32), "DB_PASSWORD": secrets.token_hex(16),
        "TEST_DB_PASSWORD": secrets.token_hex(16), "DEMO_USER_PASSWORD": secrets.token_hex(12),
        "MYSQL_ROOT_PASSWORD": secrets.token_hex(16), "HOST_UID": str(os.getuid()), "HOST_GID": str(os.getgid())}
lines = []
for line in open(".env.example", encoding="utf-8").read().splitlines():
    key = line.split("=", 1)[0]
    lines.append(f"{key}={fill[key]}" if key in fill else line)
lines += [f"WEB_PORT={port}", f"COMPOSE_PROJECT_NAME={project}"]
open(".env", "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
chmod 600 .env
set -a; . ./.env; set +a
grep -E '^[A-Z_]+=' .env | cut -d= -f1 | tr '\n' ' '; echo

step "3. docker compose up -d --build（全新数据卷）"
dc up -d --build --quiet-pull
for _ in $(seq 60); do [ "$(curl -s -o /dev/null -w '%{http_code}' "$B/")" = 200 ] && break; sleep 2; done
dc ps --format '{{.Service}} {{.Image}} {{.State}} {{.Ports}}'
run python --version

step "4. flask db upgrade"
run flask db upgrade

step "5. 导入演示内容与演示学习者"
run flask import-content data/demo/v1 | tail -n 3
run flask seed-demo-user

step "6. 公开页面与静态图片（T01）"
expect / 200
expect /lab/hello 200
IMG=$(curl -s "$B/lab/hello" | grep -o 'src="/static/[^"]*"' | head -1 | sed 's/src="//;s/"$//')
expect "$IMG" 200
expect /login 200
expect /api/v1/me 401

step "7. 答辩路径学习闭环（evidence/exp02/review-path.sh）"
BASE_URL=$B bash evidence/exp02/review-path.sh | sed 1d

step "8. 未放入模型制品：模型页不可用，学习流程照常（T13）"
T=$(tok /login); curl -s -o /dev/null -b "$J" -c "$J" -X POST --data-urlencode "csrf_token=$T" -d username=demo --data-urlencode "password=$DEMO_USER_PASSWORD" "$B/auth/login"
expect /api/v1/me 200
api POST /api/v1/ml/recall '{"delta_seconds":86400,"history_seen":5,"history_correct":4}' | show 503 ""
api POST /api/v1/examples/search '{"text":"I need to open a savings account.","top_k":3}' | show 503 ""
S=$(api POST /api/v1/practice/sessions '{"skill_type":"spelling","count":1}'); echo "$S" | show 201 status,total
for p in /lab/ml /examples; do echo "GET $p → $(curl -s -b "$J" "$B$p" | grep -o '[^>]*不可用：[^<]*' | head -1)"; done

step "9. 放入本地模型制品后登记并建索引（制品不进 Git，从源目录复制）"
mkdir -p artifacts/ml artifacts/dl
cp -r "$SRC/artifacts/ml/." artifacts/ml/
cp -r "$SRC/artifacts/dl/encoder" artifacts/dl/
run flask register-model artifacts/ml | tail -n 2
run flask build-example-index | tail -n 2
dc restart web
for _ in $(seq 60); do [ "$(curl -s -o /dev/null -w '%{http_code}' "$B/")" = 200 ] && break; sleep 2; done
api POST /api/v1/ml/recall '{"delta_seconds":86400,"history_seen":5,"history_correct":4}' | show 200 status,expected_recall
api POST /api/v1/ml/recall '{"delta_seconds":86400,"history_seen":0,"history_correct":0}' | show 200 status,expected_recall
api POST /api/v1/examples/search '{"text":"I need to open a savings account.","top_k":3}' \
  | python3 -c 'import sys,json; raw=sys.stdin.read().rstrip("\n"); body,code=raw.rsplit("\n",1); d=json.loads(body)["data"]
print("HTTP", code, [(r["example_key"], round(r["cosine_similarity"],3)) for r in d["results"]]); sys.exit(0 if code=="200" else 1)'
echo "实验四评价重跑（语料指纹含数据库 id，换库后不同；评价按 example_key 引用例句、同分按 example_key 排序，结果应与 evidence/exp04 完全一致）："
run flask evaluate-example-search --out artifacts/dl/eval-handoff | tail -n 1
python3 - "$SRC/evidence/exp04/retrieval-metrics.json" artifacts/dl/eval-handoff/metrics.json <<'PY'
import json, sys
old, new = (json.load(open(p, encoding="utf-8"))["result"] for p in sys.argv[1:])
diffs = [f"{s} {m} {qa['query_id']}" for s in old for m in old[s]
         for qa, qb in zip(old[s][m]["per_query"], new[s][m]["per_query"]) if qa != qb]
if old != new:
    print("!! 与 evidence/exp04 不一致：", "、".join(diffs) or "汇总指标")
    sys.exit(1)
print("汇总指标与逐条前三项（含分数与顺序）均与 evidence/exp04 一致")
PY
echo "推理事件（MySQL，M06）："
sql "SELECT kind, source_type, status, COUNT(*) FROM inference_events GROUP BY kind, source_type, status ORDER BY kind, source_type, status"

step "10. 完整检查：编译、ruff、pytest（db 测试使用本项目的全新测试库）、pip check"
run bash -c 'set -o pipefail; python -m compileall -q app tests ml && ruff check . && ruff format --check . && pytest -q -rs 2>&1 | tail -n 15 && pip check'

step "11. SQL 导出可导入空库（测试账户，最小权限）"
scripts/db_export.sh "$WORK/export.sql"
root -e "DROP DATABASE \`$TEST_DB_NAME\`; CREATE DATABASE \`$TEST_DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
docker compose exec -T -e MYSQL_PWD="$TEST_DB_PASSWORD" db mysql -u"$TEST_DB_USER" "$TEST_DB_NAME" <"$WORK/export.sql"
run env DB_NAME="$TEST_DB_NAME" DB_USER="$TEST_DB_USER" DB_PASSWORD="$TEST_DB_PASSWORD" flask db upgrade
diff <(counts "$DB_NAME" | grep -E '^(schema_migrations|wordbooks|words|word_senses|wordbook_words|examples|questions) ') \
     <(counts "$TEST_DB_NAME" | grep -E '^(schema_migrations|wordbooks|words|word_senses|wordbook_words|examples|questions) ') \
  && echo "内容表行数一致：$(counts "$TEST_DB_NAME" | grep -E '^(wordbooks|words|word_senses|examples|questions) ' | tr '\n' ' ')"
echo "个人记录表在导出中为空：$(counts "$TEST_DB_NAME" | grep -E '^(users|attempts|learning_state|inference_events) ' | tr '\n' ' ')"

step "12. 完整备份 → 恢复到临时库 → 逐表核对行数"
BK=$(scripts/db_backup.sh "$WORK/backups" | sed 's/^已备份：//'); echo "备份文件 $(basename "$BK")，$(wc -c <"$BK") 字节，权限 $(stat -c %a "$BK")"
scripts/db_restore.sh "$BK" vocab_review_restore
diff <(counts "$DB_NAME") <(counts vocab_review_restore) && echo "15 张表逐表行数一致：$(counts vocab_review_restore | tr '\n' ' ')"
run env DB_NAME=vocab_review_restore DB_USER=root DB_PASSWORD="$MYSQL_ROOT_PASSWORD" flask rebuild-learning-state
root -e "DROP DATABASE vocab_review_restore"

step "完成：干净环境验收全部通过"

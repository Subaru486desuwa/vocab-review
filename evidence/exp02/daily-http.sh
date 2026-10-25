#!/bin/bash
# 学习趋势留证（T16）：模拟演示账户登录 → GET /api/v1/me/daily → 参数校验 → 与今日任务、复习清单、数据库对照 → 概览页。
# 在仓库根目录、docker compose 运行时执行；账户须已由 flask seed-demo-history 生成，密码取 .env 的 DEMO_USER_PASSWORD 且不输出。
set -euo pipefail
set -a; . ./.env; set +a
B=${BASE_URL:-http://127.0.0.1:5000}
U=${1:-sim_trend}
J=$(mktemp)
sql() { docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" db mysql -u"$DB_USER" "$DB_NAME" -N -e "$1"; }
form_tok() { curl -s -b "$J" -c "$J" "$B$1" | grep -o 'name="csrf_token" value="[^"]*"' | head -1 | sed 's/.*value="//;s/"$//'; }
get() { curl -s -w '\n%{http_code}' -b "$J" -c "$J" "$B$1"; }
show() { python3 -c 'import sys,json
raw=sys.stdin.read().rstrip("\n"); body,code=raw.rsplit("\n",1); d=json.loads(body)
print("HTTP", code, json.dumps(d["error"] if d["error"] else d["data"], ensure_ascii=False))'; }

echo "# executed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) base=$B user=$U（模拟演示数据，由 flask seed-demo-history 生成，不是真实学习记录）"
echo "## 1. 未登录 GET /api/v1/me/daily"; get /api/v1/me/daily | show
echo "## 2. 登录（表单 POST /auth/login）"
T=$(form_tok /login); curl -s -o /dev/null -w "HTTP %{http_code}\n" -b "$J" -c "$J" -X POST "$B/auth/login" --data-urlencode "csrf_token=$T" -d "username=$U" --data-urlencode "password=$DEMO_USER_PASSWORD"
echo "## 3. GET /api/v1/me/daily（默认 14 天）"
D=$(get /api/v1/me/daily)
echo "$D" | head -n -1 | python3 -c 'import sys,json
d=json.load(sys.stdin)["data"]
print("timezone", d["timezone"], "天数", len(d["days"]))
print("日期        作答  正确率  新词义  首次题型  到期复习(对)  提前  日终待复习  三类之和=作答")
for r in d["days"]:
    a, v = r["attempts"], r["reviews"]
    acc = "—" if a["accuracy"] is None else "{:.0%}".format(a["accuracy"])
    print("{}  {:>4}  {:>5}  {:>6}  {:>8}  {:>6}({})  {:>4}  {:>10}  {}".format(r["date"], a["count"], acc, r["new_senses"], r["first_on_skill"], v["due"], v["due_correct"], v["early"], r["backlog_end"], r["first_on_skill"] + v["due"] + v["early"] == a["count"]))
print("totals", json.dumps(d["totals"], ensure_ascii=False))
print("granularity", d["granularity"])'
echo "## 4. days 参数"
for v in 7 0 61 abc; do printf "days=%s → " "$v"; get "/api/v1/me/daily?days=$v" | python3 -c 'import sys,json
raw=sys.stdin.read().rstrip("\n"); body,code=raw.rsplit("\n",1); d=json.loads(body)
print("HTTP", code, "{} 天".format(len(d["data"]["days"])) if d["data"] else json.dumps(d["error"]["fields"], ensure_ascii=False))'; done
echo "## 5. 与今日任务、复习清单、数据库对照（今天）"
echo "$D" | head -n -1 > /tmp/daily.json
get /api/v1/me/today | head -n -1 > /tmp/today.json
get /api/v1/me/review | head -n -1 > /tmp/review.json
UID_=$(sql "SELECT id FROM users WHERE username_norm='$U'")
FIRST=$(python3 -c 'import json; print(json.load(open("/tmp/daily.json"))["data"]["days"][0]["date"])')
# 窗口起点为上海时间 FIRST 00:00，即 UTC 前一日 16:00。
DBN=$(sql "SELECT COUNT(*) FROM attempts a JOIN session_items i ON i.id=a.session_item_id JOIN practice_sessions p ON p.id=i.session_id WHERE p.user_id=$UID_ AND a.submitted_at >= TIMESTAMP('$FIRST') - INTERVAL 8 HOUR")
python3 -c 'import json,sys
d=json.load(open("/tmp/daily.json"))["data"]; t=json.load(open("/tmp/today.json"))["data"]; r=json.load(open("/tmp/review.json"))["data"]
today=d["days"][-1]
print("今天新词义", today["new_senses"], "| /me/today new_senses.done", t["new_senses"]["done"])
print("今天日终待复习", today["backlog_end"], "| /me/review due 数", len(r["due"]))
print("窗口作答合计", d["totals"]["attempts"]["count"], "| 数据库同期作答数", sys.argv[1])' "$DBN"
echo "## 6. 概览页"
curl -s -o /tmp/dashboard.html -w "/dashboard HTTP %{http_code}\n" -b "$J" "$B/dashboard"
grep -o '<caption>近 14 天</caption>' /tmp/dashboard.html
echo "趋势行数 $(grep -c 'class="trend-row"' /tmp/dashboard.html)"
echo "## 7. 从作答记录重建学习状态并核对"
docker compose run --rm web flask rebuild-learning-state --username "$U" 2>&1 | grep -v ' Container '
rm -f "$J" /tmp/daily.json /tmp/today.json /tmp/review.json /tmp/dashboard.html

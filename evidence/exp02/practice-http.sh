#!/bin/bash
# 学习闭环留证：demo 选择六级目标、组卷、正确/错误/空答案、重放、冲突与越权。
# 需在仓库根目录、docker compose 已运行时执行；密码取自本地 .env，不输出。
set -euo pipefail
set -a; . ./.env; set +a
B=${BASE_URL:-http://127.0.0.1:5000}
J=$(mktemp); K=$(mktemp)
sql() { docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" db mysql -u"$DB_USER" "$DB_NAME" -N -e "$1"; }
tok() { curl -s -b "$1" -c "$1" "$B$2" | grep -o 'name="csrf-token" content="[^"]*"' | head -1 | sed 's/.*content="//;s/"$//'; }
api() { local jar=$1 method=$2 path=$3 body=${4:-}; local t; t=$(tok "$jar" /dashboard)
  curl -s -w '\n%{http_code}' -b "$jar" -c "$jar" -X "$method" -H "X-CSRFToken: $t" -H 'Content-Type: application/json' ${body:+-d "$body"} "$B$path"; }
show() { python3 -c 'import sys,json
raw=sys.stdin.read().rstrip("\n"); body,code=raw.rsplit("\n",1); d=json.loads(body)
keys=sys.argv[1].split(",") if len(sys.argv)>1 else []
out=d["error"] if d["error"] else ({k:d["data"][k] for k in keys} if keys else d["data"])
print("HTTP", code, json.dumps(out, ensure_ascii=False))' "$@"; }
login() { local jar=$1 user=$2 pw=$3; local t; t=$(tok "$jar" /login)
  curl -s -o /dev/null -w "HTTP %{http_code}\n" -b "$jar" -c "$jar" -X POST --data-urlencode "csrf_token=$t" -d "username=$user" --data-urlencode "password=$pw" "$B/auth/login"; }

echo "# executed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) base=$B 演示学习者 demo；内容为项目自编演示 v1"
echo "## 1. demo 登录"; login "$J" demo "$DEMO_USER_PASSWORD"
CET6=$(sql "SELECT id FROM wordbooks WHERE code='cet6-demo'")
echo "## 2. 选择六级演示词表（PUT /api/v1/me/wordbooks）"; api "$J" PUT /api/v1/me/wordbooks "{\"wordbook_ids\":[$CET6]}" | show
echo "## 3. 创建 3 题辨义练习（POST /api/v1/practice/sessions），未作答时不含答案"
S=$(api "$J" POST /api/v1/practice/sessions '{"skill_type":"recognition","count":3}')
echo "$S" | show id,status,total,answered
echo "$S" | head -n -1 | grep -qE 'option_id|accepted|answers' && echo "!! 响应含答案字段" || echo "响应不含 answers/option_id/accepted"
read -r SID I1 I2 I3 < <(echo "$S" | head -n -1 | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];print(d["id"],*[i["id"] for i in d["items"]])')
wrong_of() { sql "SELECT JSON_UNQUOTE(JSON_EXTRACT(q.options_json,'\$[0].id')), JSON_UNQUOTE(JSON_EXTRACT(q.options_json,'\$[1].id')), JSON_UNQUOTE(JSON_EXTRACT(q.answers_json,'\$.option_id')) FROM session_items i JOIN questions q ON q.id=i.question_id WHERE i.id=$1" | awk '{print ($1==$3)?$2:$1}'; }
RIGHT=$(sql "SELECT JSON_UNQUOTE(JSON_EXTRACT(q.answers_json,'\$.option_id')) FROM session_items i JOIN questions q ON q.id=i.question_id WHERE i.id=$I1")
WRONG=$(wrong_of "$I2"); WRONG1=$(wrong_of "$I1")
echo "## 4. 第 1 题正确答案"; api "$J" POST /api/v1/practice/items/$I1/answer "{\"answer\":\"$RIGHT\"}" | show is_correct,error_type,replayed,correct_answer
echo "## 5. 第 2 题错误答案"; api "$J" POST /api/v1/practice/items/$I2/answer "{\"answer\":\"$WRONG\"}" | show is_correct,error_type,replayed
echo "## 6. 第 3 题空答案"; api "$J" POST /api/v1/practice/items/$I3/answer '{"answer":""}' | show is_correct,error_type,session_status
echo "## 7. 第 1 题相同答案重放"; api "$J" POST /api/v1/practice/items/$I1/answer "{\"answer\":\"$RIGHT\"}" | show is_correct,replayed
echo "## 8. 第 1 题换答案"; api "$J" POST /api/v1/practice/items/$I1/answer "{\"answer\":\"$WRONG1\"}" | show
echo "## 9. 另一用户访问 demo 的练习与题目"
PEER="peer_$(date +%s)"; PEERPW=$(python3 -c 'import secrets;print(secrets.token_urlsafe(12))')
T=$(tok "$K" /register); curl -s -o /dev/null -b "$K" -c "$K" -X POST --data-urlencode "csrf_token=$T" -d "username=$PEER" --data-urlencode "password=$PEERPW" "$B/auth/register"
api "$K" GET /api/v1/practice/sessions/$SID | show
api "$K" POST /api/v1/practice/items/$I1/answer "{\"answer\":\"$RIGHT\"}" | show
echo "## 10. MySQL：本次练习的作答与学习状态"
sql "SELECT 'attempt', a.session_item_id, a.is_correct, IFNULL(a.error_type,'-'), a.review_rule_version FROM attempts a JOIN session_items i ON i.id=a.session_item_id WHERE i.session_id=$SID ORDER BY a.id"
sql "SELECT 'state', l.sense_id, l.seen_count, l.correct_count, l.correct_streak, l.interval_stage, TIMESTAMPDIFF(MINUTE, l.last_attempt_at, l.next_review_at) AS review_after_min FROM learning_state l JOIN questions q ON q.sense_id=l.sense_id AND q.skill_type=l.skill_type JOIN session_items i ON i.question_id=q.id WHERE i.session_id=$SID AND l.user_id=(SELECT id FROM users WHERE username_norm='demo')"
sql "SELECT 'session', status, finished_at IS NOT NULL FROM practice_sessions WHERE id=$SID"
rm -f "$J" "$K"

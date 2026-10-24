#!/bin/bash
# 今日任务留证（T15）：新注册演示账户 → 选六级 → 查看今日任务 → 10 个新词义练习（前 2 题答错）→ 再看今日任务。
# 在仓库根目录、docker compose 运行时执行；密码随机生成且不记录。
set -euo pipefail
set -a; . ./.env; set +a
B=${BASE_URL:-http://127.0.0.1:5000}
U=demo_t$(date -u +%m%d%H%M)
J=$(mktemp); PW=$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')
sql() { docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" db mysql -u"$DB_USER" "$DB_NAME" -N -e "$1"; }
form_tok() { curl -s -b "$J" -c "$J" "$B$1" | grep -o 'name="csrf_token" value="[^"]*"' | head -1 | sed 's/.*value="//;s/"$//'; }
tok() { curl -s -b "$J" -c "$J" "$B$1" | grep -o 'name="csrf-token" content="[^"]*"' | head -1 | sed 's/.*content="//;s/"$//'; }
api() { local t; t=$(tok /dashboard); curl -s -w '\n%{http_code}' -b "$J" -c "$J" -X "$1" -H "X-CSRFToken: $t" -H 'Content-Type: application/json' ${3:+-d "$3"} "$B$2"; }
show() { python3 -c 'import sys,json
raw=sys.stdin.read().rstrip("\n"); body,code=raw.rsplit("\n",1); d=json.loads(body)
keys=[k for k in sys.argv[1].split(",") if k] if len(sys.argv)>1 else []
out=d["error"] if d["error"] else ({k:d["data"][k] for k in keys} if keys else d["data"])
print("HTTP", code, json.dumps(out, ensure_ascii=False))' "$@"; }

echo "# executed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) base=$B user=$U（演示账户）；内容为项目自编演示 v1"
echo "## 1. 注册并登录（表单 POST /auth/register）"
T=$(form_tok /register); curl -s -o /dev/null -w "HTTP %{http_code}\n" -b "$J" -c "$J" -X POST "$B/auth/register" --data-urlencode "csrf_token=$T" -d "username=$U" --data-urlencode "password=$PW"
echo "## 2. 未选目标时 GET /api/v1/me/today"; api GET /api/v1/me/today | show
CET6=$(sql "SELECT id FROM wordbooks WHERE code='cet6-demo'")
echo "## 3. 只选六级目标"; api PUT /api/v1/me/wordbooks "{\"wordbook_ids\":[$CET6]}" | show wordbooks | cut -c1-80
echo "## 4. 今日任务（新账户）"; api GET /api/v1/me/today | show
echo "## 5. 学今日新词：POST /api/v1/practice/sessions focus=new_senses count=10"
S=$(api POST /api/v1/practice/sessions '{"skill_type":"recognition","count":10,"focus":"new_senses"}')
echo "$S" | show id,focus,skill_type,total
N=0
for item in $(echo "$S" | head -n -1 | python3 -c 'import sys,json; print(" ".join(str(i["id"]) for i in json.load(sys.stdin)["data"]["items"]))'); do
  read -r A O1 O2 < <(sql "SELECT JSON_UNQUOTE(JSON_EXTRACT(q.answers_json,'\$.option_id')), JSON_UNQUOTE(JSON_EXTRACT(q.options_json,'\$[0].id')), JSON_UNQUOTE(JSON_EXTRACT(q.options_json,'\$[1].id')) FROM session_items i JOIN questions q ON q.id=i.question_id WHERE i.id=$item")
  N=$((N+1)); if [ $N -le 2 ]; then V=$([ "$O1" = "$A" ] && echo "$O2" || echo "$O1"); else V=$A; fi
  api POST "/api/v1/practice/items/$item/answer" "{\"answer\":\"$V\"}" | show lemma,is_correct,session_status
done
echo "## 6. 今日任务（10 个新词义已完成，2 个错题约 10 分钟后到期）"; api GET /api/v1/me/today | show
echo "## 7. 再学新词：只出任何题型都未作答的词义"
api POST /api/v1/practice/sessions '{"skill_type":"recognition","count":20,"focus":"new_senses"}' | head -n -1 | python3 -c 'import sys,json; d=json.load(sys.stdin)["data"]; print("题数", d["total"], "focus", d["focus"])'
UID_=$(sql "SELECT id FROM users WHERE username_norm='$(echo "$U" | tr A-Z a-z)'")
echo "与已作答词义重叠：$(sql "SELECT COUNT(*) FROM session_items i JOIN questions q ON q.id=i.question_id WHERE i.session_id=(SELECT MAX(id) FROM practice_sessions WHERE user_id=$UID_) AND q.sense_id IN (SELECT q2.sense_id FROM attempts a JOIN session_items i2 ON i2.id=a.session_item_id JOIN practice_sessions p ON p.id=i2.session_id JOIN questions q2 ON q2.id=i2.question_id WHERE p.user_id=$UID_)") 题"
echo "## 8. 非法 focus"; api POST /api/v1/practice/sessions '{"skill_type":"recognition","count":5,"focus":"hard"}' | show
echo "## 9. 页面"
curl -s -o /tmp/today.html -w "/today HTTP %{http_code}\n" -b "$J" "$B/today"
grep -o '连续学习</dt><dd>[^<]*\|今日新词义</dt><dd>[^<]*\|待复习</dt><dd>[^<]*' /tmp/today.html | sed 's/<\/dt><dd>/ /'
grep -c 'href="/today"' <(curl -s -b "$J" "$B/dashboard") | sed 's/^/概览页“今日任务”入口数 /'
echo "## 10. 从作答记录重建学习状态并核对"
docker compose run --rm web flask rebuild-learning-state --username "$U" 2>&1 | grep -v ' Container '
rm -f "$J" /tmp/today.html

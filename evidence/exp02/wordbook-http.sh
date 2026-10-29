#!/bin/bash
# 考研正式词表与成对记忆留证（#49，ADR 0004）：新账户 → 选考研词表（ECDICT）→ 辨义练习，首题答错、其余答对
# （答错的是第一个有词对的词）→ 反馈中的词对 → 诊断页成对复习建议 → 按建议发起成对练习（选题理由 targeted）。
# 在仓库根目录、docker compose 运行时执行；账户名带时间戳，密码随机生成且不输出。
set -euo pipefail
set -a; . ./.env; set +a
B=${BASE_URL:-http://127.0.0.1:5000}
U=ky_check_$(date -u +%m%d%H%M%S)
PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
J=$(mktemp)
O=$(mktemp)
trap 'rm -f "$J" "$O"' EXIT
sql() { docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" db mysql --default-character-set=utf8mb4 -u"$DB_USER" "$DB_NAME" -N -e "$1"; }
tok() { curl -s -b "$J" -c "$J" "$B$1" | grep -o 'name="csrf-token" content="[^"]*"' | head -1 | sed 's/.*content="//;s/"$//'; }
api() { local method=$1 path=$2 body=${3:-}; local t; t=$(tok /dashboard)
  curl -s -o "$O" -w '%{http_code}' -b "$J" -c "$J" -X "$method" -H "X-CSRFToken: $t" -H 'Content-Type: application/json' ${body:+-d "$body"} "$B$path"; }

echo "# executed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) base=$B user=$U（留证账户）"
echo "## 1. 内容表计数"
sql "SELECT code, version, name, (SELECT COUNT(*) FROM wordbook_words m WHERE m.wordbook_id = b.id) AS words FROM wordbooks b WHERE code = 'ky-ecdict'"
sql "SELECT relation_type, COUNT(*) FROM word_relations GROUP BY relation_type ORDER BY relation_type"
echo "## 2. 注册并选择考研词表"
T=$(tok /register); curl -s -o /dev/null -w "POST /auth/register HTTP %{http_code}\n" -b "$J" -c "$J" -X POST --data-urlencode "csrf_token=$T" -d "username=$U" --data-urlencode "password=$PW" "$B/auth/register"
KY=$(sql "SELECT id FROM wordbooks WHERE code = 'ky-ecdict' AND version = 'v1'")
echo "PUT /api/v1/me/wordbooks HTTP $(api PUT /api/v1/me/wordbooks "{\"wordbook_ids\":[$KY]}")"
echo "## 3. 辨义练习 10 题：第一个有词对的词答错、其余答对"
echo "POST /api/v1/practice/sessions HTTP $(api POST /api/v1/practice/sessions '{"skill_type":"recognition","count":10}')"
ITEMS=$(python3 -c "import json,sys; print(' '.join(str(i['id']) for i in json.load(open(sys.argv[1]))['data']['items']))" "$O")
WRONG=$(sql "SELECT i.id FROM session_items i JOIN questions q ON q.id = i.question_id JOIN word_senses s ON s.id = q.sense_id
  WHERE i.id IN (${ITEMS// /,}) AND EXISTS (SELECT 1 FROM word_relations r WHERE s.word_id IN (r.word_id_a, r.word_id_b))
  ORDER BY i.position LIMIT 1")
for item in $ITEMS; do
  pick=$([ "$item" = "$WRONG" ] && echo "<>" || echo "=")
  ans=$(sql "SELECT JSON_UNQUOTE(o.id) FROM session_items i JOIN questions q ON q.id = i.question_id,
    JSON_TABLE(q.options_json, '\$[*]' COLUMNS (id VARCHAR(8) PATH '\$.id')) o
    WHERE i.id = $item AND o.id $pick JSON_UNQUOTE(JSON_EXTRACT(q.answers_json, '\$.option_id')) LIMIT 1")
  code=$(api POST "/api/v1/practice/items/$item/answer" "{\"answer\":\"$ans\"}")
  python3 - "$O" "$code" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))["data"]
related = "；".join(f"{'·'.join(e['types'])} {e['lemma']}" for e in r["related"]) or "无"
print(f"HTTP {sys.argv[2]} {r['lemma']}：{'✓' if r['is_correct'] else '✗'} 词对：{related}")
PY
done
echo "## 4. 诊断：当前弱项与成对复习建议"
echo "GET /api/v1/me/insights HTTP $(api GET /api/v1/me/insights)"
python3 - "$O" > "$O.pairs" <<'PY'
import json, sys
cur = json.load(open(sys.argv[1]))["data"]["current"]
print("weak", [(e["lemma"], e["skill_type"]) for e in cur["weak"]], file=sys.stderr)
for p in cur["pairs"]:
    partners = "、".join(f"{'·'.join(x['types'])} {x['lemma']}（{x['status']}）" for x in p["partners"])
    print(f"pairs {p['lemma']} {p['skill_type']}：{partners} sense_ids={p['sense_ids']}", file=sys.stderr)
if cur["pairs"]:
    print(json.dumps({"skill_type": cur["pairs"][0]["skill_type"], "count": len(cur["pairs"][0]["sense_ids"]),
                      "sense_ids": cur["pairs"][0]["sense_ids"]}))
PY
BODY=$(cat "$O.pairs"); rm -f "$O.pairs"
if [ -n "$BODY" ]; then
  echo "## 5. 成对练习"
  echo "POST /api/v1/practice/sessions HTTP $(api POST /api/v1/practice/sessions "$BODY")"
  python3 -c "import json,sys; d=json.load(open(sys.argv[1]))['data']; print('items', len(d['items']), 'reasons', sorted({i['reason']['code'] for i in d['items']}))" "$O"
else
  echo "## 5. 弱项在目标范围内没有词对，跳过成对练习"
fi
curl -s -b "$J" "$B/insights" | grep -o '成对复习[^<]*' | head -1

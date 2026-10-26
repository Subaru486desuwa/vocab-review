#!/bin/bash
# 答辩路径留证：登录 → 六级目标 → 含错误练习 → 复习计划 → 增加雅思并展示历史复用 → 学习状态重建核对。
# 在仓库根目录、docker compose 运行时执行；密码取自本地 .env，不输出。
set -euo pipefail
set -a; . ./.env; set +a
B=${BASE_URL:-http://127.0.0.1:5000}
J=$(mktemp)
sql() { docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" db mysql -u"$DB_USER" "$DB_NAME" -N -e "$1"; }
tok() { curl -s -b "$J" -c "$J" "$B$1" | grep -o 'name="csrf-token" content="[^"]*"' | head -1 | sed 's/.*content="//;s/"$//'; }
api() { local t; t=$(tok /dashboard); curl -s -b "$J" -c "$J" -X "$1" -H "X-CSRFToken: $t" -H 'Content-Type: application/json' ${3:+-d "$3"} "$B$2"; }
py() { python3 -c "import sys,json; d=json.load(sys.stdin)['data']; $1"; }

echo "# executed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) base=$B 演示学习者 demo；内容为项目自编演示 v1/v2/v3"
echo "## 1. 登录"
T=$(tok /login); curl -s -o /dev/null -w "HTTP %{http_code}\n" -b "$J" -c "$J" -X POST --data-urlencode "csrf_token=$T" -d username=demo --data-urlencode "password=$DEMO_USER_PASSWORD" "$B/auth/login"
CET6=$(sql "SELECT id FROM wordbooks WHERE code='cet6-demo'"); IELTS=$(sql "SELECT id FROM wordbooks WHERE code='ielts-demo'")
echo "## 2. 只选六级目标"
api PUT /api/v1/me/wordbooks "{\"wordbook_ids\":[$CET6]}" | py 'print([b["code"] for b in d["wordbooks"]])'
echo "## 3. 5 题辨义练习：前 2 题故意答错，其余答对"
S=$(api POST /api/v1/practice/sessions '{"skill_type":"recognition","count":5}')
for item in $(echo "$S" | py 'print(" ".join(str(i["id"]) for i in d["items"]))'); do
  read -r A O1 O2 < <(sql "SELECT JSON_UNQUOTE(JSON_EXTRACT(q.answers_json,'\$.option_id')), JSON_UNQUOTE(JSON_EXTRACT(q.options_json,'\$[0].id')), JSON_UNQUOTE(JSON_EXTRACT(q.options_json,'\$[1].id')) FROM session_items i JOIN questions q ON q.id=i.question_id WHERE i.id=$item")
  N=${N:-0}; N=$((N+1)); if [ $N -le 2 ]; then V=$([ "$O1" = "$A" ] && echo "$O2" || echo "$O1"); else V=$A; fi
  api POST /api/v1/practice/items/$item/answer "{\"answer\":\"$V\"}" | py 'print(d["lemma"], "正确" if d["is_correct"] else "错误("+d["error_type"]+")", "→", d["session_status"])'
done
echo "## 4. 复习计划（GET /api/v1/me/review）"
api GET /api/v1/me/review | py '
print("已到期", len(d["due"]), "；未到期错题", len(d["wrong_pending"]), "；下一项到期", d["next_due_at"])
[print("  错题", e["lemma"], e["skill_type"], "约", round(e["seconds_until_due"]/60), "分钟后到期") for e in d["wrong_pending"][:5]]'
echo "## 5. 六级目标统计（GET /api/v1/me/stats）"
api GET /api/v1/me/stats | py 'print("词条 已练习/总数", d["words"]["practiced"], "/", d["words"]["total"], "；词义×题型 已测试/未测试/总数", d["items"]["tested"], d["items"]["untested"], d["items"]["total"], "；作答", d["attempts"]["all_time"])'
echo "## 6. 增加雅思目标（六级 + 雅思）"
api PUT /api/v1/me/wordbooks "{\"wordbook_ids\":[$CET6,$IELTS]}" | py 'print([b["code"] for b in d["wordbooks"]])'
api GET /api/v1/me/stats | py 'print("合计词条（共有词只计一次）", d["words"]["total"]); [print("  ", b["code"], "词条", b["words_total"], "已练习", b["words_practiced"]) for b in d["by_wordbook"]]'
echo "## 7. 只看雅思词表：共有词条在六级目标下的作答被复用"
api GET "/api/v1/me/stats?wordbook_id=$IELTS" | py 'print("雅思 已练习词条", d["words"]["practiced"], "/", d["words"]["total"], "；作答", d["attempts"]["all_time"], "；未测试", d["items"]["untested"])'
echo "## 8. 页面"
for p in /dashboard /review; do curl -s -o /dev/null -w "$p HTTP %{http_code}\n" -b "$J" "$B$p"; done
echo "## 9. 从作答记录重建学习状态并核对（flask rebuild-learning-state）"
docker compose run --rm web flask rebuild-learning-state 2>&1 | grep -v ' Container '
rm -f "$J"

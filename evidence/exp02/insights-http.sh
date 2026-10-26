#!/bin/bash
# 学习诊断留证（T17）：未登录 → 模拟演示账户登录 → GET /api/v1/me/insights（两次，记录首次加载与预热后耗时）
# → 与数据库作答事实对照 → 只读核对 → 推理事件 → 诊断页。
# 在仓库根目录、docker compose 运行时执行；账户须已由 flask seed-demo-history 生成，密码取 .env 的 DEMO_USER_PASSWORD 且不输出。
set -euo pipefail
set -a; . ./.env; set +a
B=${BASE_URL:-http://127.0.0.1:5000}
U=${1:-sim_trend}
J=$(mktemp)
O=$(mktemp)
sql() { docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" db mysql -u"$DB_USER" "$DB_NAME" -N -e "$1"; }
form_tok() { curl -s -b "$J" -c "$J" "$B$1" | grep -o 'name="csrf_token" value="[^"]*"' | head -1 | sed 's/.*value="//;s/"$//'; }

echo "# executed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) base=$B user=$U（模拟演示数据，由 flask seed-demo-history 生成，不是真实学习记录）"
echo "## 1. 未登录"
curl -s -o /dev/null -w "GET /api/v1/me/insights HTTP %{http_code}\n" "$B/api/v1/me/insights"
curl -s -o /dev/null -w "GET /insights HTTP %{http_code}（跳转登录）\n" "$B/insights"
echo "## 2. 登录（表单 POST /auth/login）"
T=$(form_tok /login); curl -s -o /dev/null -w "HTTP %{http_code}\n" -b "$J" -c "$J" -X POST "$B/auth/login" --data-urlencode "csrf_token=$T" -d "username=$U" --data-urlencode "password=$DEMO_USER_PASSWORD"
UID_=$(sql "SELECT id FROM users WHERE username_norm='$U'")
BEFORE=$(sql "SELECT (SELECT COUNT(*) FROM attempts), (SELECT COALESCE(SUM(seen_count),0) FROM learning_state), (SELECT MAX(id) FROM inference_events)")
LAST_EVENT=$(echo "$BEFORE" | awk '{print $3}'); LAST_EVENT=${LAST_EVENT/NULL/0}
echo "## 3. GET /api/v1/me/insights（第一次含模型加载，第二次为预热后）"
curl -s -b "$J" -o "$O" -w "第一次 HTTP %{http_code} %{time_total}s\n" "$B/api/v1/me/insights"
curl -s -b "$J" -o "$O" -w "第二次 HTTP %{http_code} %{time_total}s\n" "$B/api/v1/me/insights"
python3 - "$O" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))["data"]
r = d["rules"]
print("attempts", json.dumps(d["attempts"]))
print("error_types", json.dumps(r["error_types"]))
print("spelling", json.dumps(r["spelling"]["counts"]))
print("most_wrong 前 5", [(e["lemma"], e["wrong"], e["attempts"]) for e in r["most_wrong"][:5]])
matched = sum(1 for c in r["confusions"] if c["chosen_sense"])
print("误选选项", len(r["confusions"]), "组，次数", sum(c["count"] for c in r["confusions"]), "；可对应回词义", matched, "组")
ml = d["ml"]
print("ML", ml["status"], json.dumps(ml.get("model"), ensure_ascii=False), "items", ml.get("items"), "model_time_ms", ml.get("model_time_ms"))
for e in ml.get("risk", [])[:5]:
    print("  遗忘风险", e["lemma"], e["skill_type"], "距上次", e["days_since"], "天", e["correct"], "/", e["seen"], "expected_recall", e["expected_recall"])
for g in ml.get("groups") or []:
    print("  分组", g["name"], g["count"], "项 平均预期", g["mean_expected_recall"], "正确率", g["mean_accuracy"], "距上次", g["mean_days_since"], "天")
dl = d["dl"]
print("DL", dl["status"], json.dumps(dl.get("model"), ensure_ascii=False), "错题词义", dl.get("wrong_senses"), "threshold", dl.get("threshold"), "model_time_ms", dl.get("model_time_ms"))
for g in dl.get("groups", []):
    print("  语义组", [m["lemma"] + "#" + m["sense_key"] for m in g["members"]], "组内平均相似度", g["cohesion"])
print("  误选：语义相近", dl.get("similar_count"), "次；相关度低", dl.get("low_count"), "次")
for c in sorted(dl.get("confusions", []), key=lambda c: -c["similarity"])[:3]:
    print("  相似度最高", c["sense"]["lemma"], c["correct"], "→", c["chosen"], c["similarity"])
json.dump(d["attempts"], open(sys.argv[1] + ".attempts", "w"))
PY
echo "## 4. 与数据库作答事实对照"
DB=$(sql "SELECT COUNT(*), SUM(NOT a.is_correct) FROM attempts a JOIN session_items i ON i.id=a.session_item_id JOIN practice_sessions p ON p.id=i.session_id WHERE p.user_id=$UID_")
echo "接口 $(cat "$O.attempts") | 数据库 作答 答错：$DB"
echo "## 5. 只读核对（全部作答数、全部 seen_count 之和）"
AFTER=$(sql "SELECT (SELECT COUNT(*) FROM attempts), (SELECT COALESCE(SUM(seen_count),0) FROM learning_state)")
echo "访问前 $(echo "$BEFORE" | awk '{print $1, $2}') | 访问后 $AFTER"
echo "## 6. 本次产生的推理事件（两次请求各一条 ml、一条 dl）"
sql "SELECT e.id, e.kind, e.source_type, e.status, m.model_code, LEFT(m.version, 12) AS version, e.model_time_ms, e.processing_time_ms, JSON_LENGTH(e.input_json, '\$.items') AS ml_items, JSON_LENGTH(e.input_json, '\$.sense_ids') AS dl_senses FROM inference_events e LEFT JOIN model_versions m ON m.id = e.model_version_id WHERE e.id > $LAST_EVENT ORDER BY e.id"
echo "## 7. 诊断页"
curl -s -o "$O" -w "/insights HTTP %{http_code}\n" -b "$J" "$B/insights"
for s in 选错的选项 拼写错法 遗忘风险 错题语义 方法说明; do printf "%s：%s\n" "$s" "$(grep -c "$s" "$O")"; done
rm -f "$J" "$O" "$O.attempts"

#!/bin/bash
# 实验二 HTTP 留证：演示账户 demo_e2，密码随机生成且不记录。
set -euo pipefail
B=http://127.0.0.1:5000
J=$(mktemp); PW=$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')
token() { curl -s -b "$J" -c "$J" "$B$1" | grep -o 'name="csrf_token" value="[^"]*"' | head -1 | sed 's/.*value="//;s/"$//'; }
show() { echo "## $1"; }
req() { curl -s -o /tmp/e2body -w "HTTP %{http_code} Location=%{redirect_url}\n" -b "$J" -c "$J" "$@"; }
echo "# executed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) base=$B user=demo_e2（演示账户）"
show "1. 注册 demo_e2（表单 POST /auth/register，含 CSRF）"
T=$(token /register); req -X POST "$B/auth/register" --data-urlencode "csrf_token=$T" -d username=demo_e2 --data-urlencode "password=$PW"
show "2. 已登录访问 /api/v1/me"; req "$B/api/v1/me"; python3 -c 'import json;d=json.load(open("/tmp/e2body"));d["request_id"]="…";print(json.dumps(d,ensure_ascii=False))'
show "3. 退出（POST /auth/logout）"; T=$(token /dashboard); req -X POST "$B/auth/logout" --data-urlencode "csrf_token=$T"
show "4. 退出后访问 /api/v1/me"; req "$B/api/v1/me"; python3 -c 'import json;d=json.load(open("/tmp/e2body"));print(d["error"])'
show "5. 错误密码登录"; T=$(token /login); req -X POST "$B/auth/login" --data-urlencode "csrf_token=$T" -d username=demo_e2 -d password=wrong-password; grep -o '用户名或密码错误' /tmp/e2body | head -1
show "6. 不存在的用户登录"; T=$(token /login); req -X POST "$B/auth/login" --data-urlencode "csrf_token=$T" -d username=no_such_user --data-urlencode "password=$PW"; grep -o '用户名或密码错误' /tmp/e2body | head -1
show "7. 正确密码登录（用户名大写，验证规范化）"; T=$(token /login); req -X POST "$B/auth/login" --data-urlencode "csrf_token=$T" -d username=DEMO_E2 --data-urlencode "password=$PW"
show "8. 重复注册（不区分大小写）"; T=$(token /register); req -X POST "$B/auth/register" --data-urlencode "csrf_token=$T" -d username=Demo_E2 --data-urlencode "password=$PW"; grep -o '用户名已被使用' /tmp/e2body | head -1
show "9. 缺少 CSRF 的登录请求"; req -X POST "$B/auth/login" -H 'Content-Type: application/json' -d '{"username":"demo_e2","password":"x"}'; python3 -c 'import json;print(json.load(open("/tmp/e2body"))["error"])'
show "10. GET /auth/logout 不改变登录状态"; req "$B/auth/logout"; req "$B/api/v1/me"
rm -f "$J" /tmp/e2body

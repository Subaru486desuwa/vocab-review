"""实验三耗时测量：独立 HTTP 客户端以演示学习者登录，先发一次请求（含首次加载），
再用固定输入顺序请求 30 次，报告 HTTP 往返与服务端 model_time_ms / processing_time_ms 的 p50/p95。

用法（仓库根目录，web 服务刚重启、尚未加载模型）：python3 evidence/exp03/latency.py
密码取自 .env 的 DEMO_USER_PASSWORD，不输出。
"""

import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:5000"
INPUTS = [(3600, 1, 1), (86400, 5, 4), (7 * 86400, 50, 45), (30 * 86400, 20, 10), (2 * 86400, 8, 3)]
RUNS = 30


def env(name):
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1]
    raise SystemExit(f".env 缺少 {name}")


opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def csrf(path):
    html = opener.open(BASE + path).read().decode()
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


def login():
    data = urllib.parse.urlencode(
        {"csrf_token": csrf("/login"), "username": env("DEMO_USERNAME"), "password": env("DEMO_USER_PASSWORD")}
    ).encode()
    opener.open(BASE + "/auth/login", data)


def recall(token, inputs):
    body = json.dumps(dict(zip(("delta_seconds", "history_seen", "history_correct"), inputs, strict=True))).encode()
    request = urllib.request.Request(
        BASE + "/api/v1/ml/recall", body, {"Content-Type": "application/json", "X-CSRFToken": token}
    )
    started = time.perf_counter()
    payload = json.loads(opener.open(request).read())
    return (time.perf_counter() - started) * 1000, payload


def pct(values, q):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))], 3)


def summary(values):
    return {"p50": pct(values, 0.5), "p95": pct(values, 0.95), "max": round(max(values), 3)}


def main():
    login()
    token = csrf("/dashboard")  # 不经过 /lab/ml，避免页面先加载模型
    first_http, first = recall(token, INPUTS[0])
    runs = [recall(token, INPUTS[i % len(INPUTS)]) for i in range(RUNS)]
    ok = [p["data"] for _, p in runs if p["error"] is None and p["data"]["status"] == "ok"]
    result = {
        "executed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "first_request": {
            "http_ms": round(first_http, 3),
            "processing_time_ms": first["data"]["processing_time_ms"],
            "model_time_ms": first["data"]["model_time_ms"],
            "note": "web 进程重启后的第一次请求，processing_time_ms 含模型校验与加载",
        },
        "warm": {
            "requests": RUNS,
            "failures": RUNS - len(ok),
            "http_ms": summary([h for h, _ in runs]),
            "processing_time_ms": summary([d["processing_time_ms"] for d in ok]),
            "model_time_ms": summary([d["model_time_ms"] for d in ok]),
        },
        "request_ids": [p["request_id"] for _, p in [(first_http, first), *runs]],
        "outputs": sorted({(i, d["expected_recall"]) for i, d in zip(INPUTS * 6, ok, strict=False)}),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

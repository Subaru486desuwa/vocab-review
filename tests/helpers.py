"""练习、复习与统计测试共用的辅助函数。"""

import json
from datetime import datetime
from pathlib import Path

from app.repositories import db
from app.services import accounts

NOW = datetime(2026, 10, 24, 0, 0, 0)
DEMO = Path(__file__).resolve().parents[1] / "data" / "demo" / "v1"
PASSWORD = "correct horse"


def query(config, sql, params=()):
    conn = db.connect(config)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def login_as(app, username):
    with app.app_context(), db.transaction() as conn:
        accounts.register(conn, username, PASSWORD, NOW)
    client = app.test_client()
    assert client.post("/auth/login", data={"username": username, "password": PASSWORD}).status_code == 302
    return client


def wordbook_ids(config, *codes):
    rows = query(config, "SELECT id, code FROM wordbooks")
    by_code = {r["code"]: r["id"] for r in rows}
    return [by_code[c] for c in codes]


def select(client, config, *codes):
    response = client.put("/api/v1/me/wordbooks", json={"wordbook_ids": wordbook_ids(config, *codes)})
    assert response.status_code == 200, response.get_json()
    return response


def start(client, skill_type="recognition", count=10, **extra):
    return client.post("/api/v1/practice/sessions", json={"skill_type": skill_type, "count": count, **extra})


def answer(client, item_id, value):
    return client.post(f"/api/v1/practice/items/{item_id}/answer", json={"answer": value})


def question_of(config, item_id):
    row = query(
        config,
        "SELECT q.*, w.lemma_norm FROM session_items i JOIN questions q ON q.id = i.question_id"
        " JOIN word_senses s ON s.id = q.sense_id JOIN words w ON w.id = s.word_id WHERE i.id = %s",
        (item_id,),
    )[0]
    row["answers"] = json.loads(row["answers_json"])
    return row


def right(config, item_id):
    q = question_of(config, item_id)
    return q["answers"].get("option_id") or q["answers"]["accepted"][0]


def wrong(config, item_id):
    q = question_of(config, item_id)
    return next(o["id"] for o in json.loads(q["options_json"]) if o["id"] != q["answers"]["option_id"])


def issue_until(client, config, skill_type, wanted, key="lemma_norm", attempts=15):
    """反复组卷直到 wanted 中的每个值（题目的 key 列）都出现过；返回 值 → 题目实例 id。"""
    found = {}
    for _ in range(attempts):
        for item in start(client, skill_type, 20).get_json()["data"]["items"]:
            lemma = question_of(config, item["id"])[key]
            if lemma in wanted:
                found.setdefault(lemma, item["id"])
        if set(wanted) <= set(found):
            return found
    raise AssertionError(f"组卷 {attempts} 次仍未覆盖：{set(wanted) - set(found)}")

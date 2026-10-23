from datetime import datetime, timedelta

import pytest

from app.repositories import db
from tests.helpers import answer, issue_until, query, question_of, right, select, start, wordbook_ids, wrong

pytestmark = pytest.mark.db

T0 = datetime(2026, 11, 2, 8, 0, 0)


def at(app, moment):
    app.config["CLOCK"] = lambda: moment


def review(client, **params):
    return client.get("/api/v1/me/review", query_string=params)


def stats(client, **params):
    return client.get("/api/v1/me/stats", query_string=params)


def senses_in(items):
    return [(e["sense_id"], e["skill_type"]) for e in items]


def user_id(config, name="alice"):
    return query(config, "SELECT id FROM users WHERE username_norm = %s", (name,))[0]["id"]


def record_attempt(config, uid, question_id, is_correct, moment, rule="review_rules_v1"):
    """直接写入一条作答事实（含练习与题目实例），不更新学习状态。"""
    conn = db.connect(config)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO practice_sessions (user_id, target_snapshot_json, status, started_at)"
            " VALUES (%s, '{}', 'completed', %s)",
            (uid, moment),
        )
        cur.execute(
            "INSERT INTO session_items (session_id, question_id, position, issued_at, submitted_at)"
            " VALUES (%s, %s, 1, %s, %s)",
            (cur.lastrowid, question_id, moment, moment),
        )
        cur.execute(
            "INSERT INTO attempts (session_item_id, raw_answer_json, normalized_answer, is_correct, error_type,"
            " review_rule_version, submitted_at) VALUES (%s, '{}', 'x', %s, %s, %s, %s)",
            (cur.lastrowid, is_correct, None if is_correct else "meaning", rule, moment),
        )
    conn.commit()
    conn.close()


def recognition_question(config, lemma):
    return query(
        config,
        "SELECT q.id, q.sense_id FROM questions q JOIN word_senses s ON s.id = q.sense_id"
        " JOIN words w ON w.id = s.word_id"
        " WHERE w.lemma_norm = %s AND q.skill_type = 'recognition' ORDER BY s.sense_key LIMIT 1",
        (lemma,),
    )[0]


# 复习清单


def test_review_lists_wrong_items_with_countdown_then_due(demo, learner, db_config):
    at(demo, T0)
    items = start(learner, "recognition", 2).get_json()["data"]["items"]
    answer(learner, items[0]["id"], wrong(db_config, items[0]["id"]))
    answer(learner, items[1]["id"], right(db_config, items[1]["id"]))
    missed = (question_of(db_config, items[0]["id"])["sense_id"], "recognition")
    known = (question_of(db_config, items[1]["id"])["sense_id"], "recognition")

    data = review(learner).get_json()["data"]
    assert data["due"] == [] and senses_in(data["wrong_pending"]) == [missed]
    entry = data["wrong_pending"][0]
    assert entry["seconds_until_due"] == 600 and entry["next_review_at"] == "2026-11-02T08:10:00Z"
    assert entry["lemma"] and entry["definition_zh"] and data["next_due_at"] == "2026-11-02T08:10:00Z"

    at(demo, T0 + timedelta(minutes=11))
    data = review(learner).get_json()["data"]
    assert senses_in(data["due"]) == [missed] and data["wrong_pending"] == []

    at(demo, T0 + timedelta(days=1, seconds=1))
    assert set(senses_in(review(learner).get_json()["data"]["due"])) == {missed, known}


def test_review_filters_and_requires_target(demo, learner, db_config):
    from tests.helpers import login_as

    at(demo, T0)
    for skill in ("recognition", "spelling"):
        item = start(learner, skill, 1).get_json()["data"]["items"][0]
        answer(learner, item["id"], wrong(db_config, item["id"]) if skill == "recognition" else "zzz")
    only = review(learner, skill_type="spelling").get_json()["data"]
    assert {e["skill_type"] for e in only["wrong_pending"]} == {"spelling"}
    assert review(learner, skill_type="essay").status_code == 422
    assert review(learner, wordbook_id=wordbook_ids(db_config, "ielts-demo")[0]).status_code == 422
    fresh = login_as(demo, "bob")
    assert review(fresh).get_json()["error"]["code"] == "NO_TARGET"


# 统计与分母


def test_stats_without_attempts_reports_untested_not_zero_scores(learner):
    data = stats(learner).get_json()["data"]
    assert (data["words"]["total"], data["words"]["practiced"]) == (30, 0)
    assert data["items"]["total"] == 35 * 3 and data["items"]["untested"] == 105 and data["items"]["tested"] == 0
    assert data["attempts"]["all_time"] == {"count": 0, "correct": 0, "accuracy": None}
    assert all(key in data["words"] and key in data["items"] for key in ("granularity",))
    assert stats(learner, skill_type="recognition").get_json()["data"]["items"]["total"] == 35


def test_stats_count_real_attempts(demo, learner, db_config):
    at(demo, T0)
    items = start(learner, "recognition", 2).get_json()["data"]["items"]
    answer(learner, items[0]["id"], right(db_config, items[0]["id"]))
    answer(learner, items[1]["id"], wrong(db_config, items[1]["id"]))
    data = stats(learner).get_json()["data"]
    words = {question_of(db_config, i["id"])["lemma_norm"] for i in items}
    assert data["attempts"]["all_time"] == {"count": 2, "correct": 1, "accuracy": 0.5}
    assert data["attempts"]["last_7_days"]["count"] == 2
    assert (data["items"]["tested"], data["items"]["untested"], data["items"]["wrong_pending"]) == (2, 103, 1)
    assert data["words"]["practiced"] == len(words)
    assert data["by_skill"]["recognition"]["attempts"]["all_time"]["count"] == 2
    assert data["by_skill"]["spelling"]["items"]["tested"] == 0
    at(demo, T0 + timedelta(days=8))
    assert stats(learner).get_json()["data"]["attempts"]["last_7_days"]["count"] == 0


def test_recently_consistent_needs_three_correct_spanning_a_day(demo, learner, db_config):
    uid = user_id(db_config)
    plans = {
        "ambiguous": [(True, 0), (True, 12), (True, 25)],
        "notion": [(True, 0), (True, 1), (True, 2)],
        "fragile": [(True, 0), (False, 1), (True, 2), (True, 14), (True, 27)],
        "emerge": [(True, 0), (True, 12), (True, 25), (False, 26)],
    }
    for lemma, plan in plans.items():
        question = recognition_question(db_config, lemma)
        for is_correct, hours in plan:
            record_attempt(db_config, uid, question["id"], is_correct, T0 + timedelta(hours=hours))
    at(demo, T0 + timedelta(days=2))
    assert stats(learner).get_json()["data"]["items"]["recently_consistent"] == 2


# T09：多目标与历史复用


def test_multiple_targets_dedupe_words_and_reuse_history(demo, learner, db_config):
    at(demo, T0)
    found = issue_until(learner, db_config, "recognition", ("abandon", "ambiguous"))
    answer(learner, found["abandon"], wrong(db_config, found["abandon"]))
    answer(learner, found["ambiguous"], right(db_config, found["ambiguous"]))

    select(learner, db_config, "cet6-demo", "ielts-demo")
    both = stats(learner).get_json()["data"]
    assert both["words"]["total"] == 50  # 30 + 30 − 10 个共有词
    assert {b["code"]: b["words_total"] for b in both["by_wordbook"]} == {"cet6-demo": 30, "ielts-demo": 30}
    assert both["attempts"]["all_time"]["count"] == 2

    select(learner, db_config, "ielts-demo")
    ielts = stats(learner).get_json()["data"]
    assert ielts["attempts"]["all_time"]["count"] == 1 and ielts["items"]["tested"] == 1
    assert ielts["items"]["untested"] == ielts["items"]["total"] - 1
    assert len(query(db_config, "SELECT * FROM attempts")) == 2
    pending = review(learner).get_json()["data"]["wrong_pending"]
    assert [e["lemma"] for e in pending] == ["abandon"]
    reissued = start(learner, "recognition", 1).get_json()["data"]["items"][0]
    assert question_of(db_config, reissued["id"])["lemma_norm"] == "abandon"


# T14：从作答记录重建学习状态


def _answer_mixed_history(demo, learner, db_config):
    at(demo, T0)
    items = start(learner, "recognition", 3).get_json()["data"]["items"]
    answer(learner, items[0]["id"], wrong(db_config, items[0]["id"]))
    answer(learner, items[1]["id"], right(db_config, items[1]["id"]))
    answer(learner, items[2]["id"], "")
    at(demo, T0 + timedelta(minutes=11))
    again = start(learner, "recognition", 2).get_json()["data"]["items"]
    for item in again:
        answer(learner, item["id"], right(db_config, item["id"]))
    at(demo, T0 + timedelta(days=1, hours=1))
    item = start(learner, "spelling", 1).get_json()["data"]["items"][0]
    answer(learner, item["id"], right(db_config, item["id"]))


def test_rebuild_agrees_with_projection_and_repairs_drift(demo, learner, db_config):
    _answer_mixed_history(demo, learner, db_config)
    runner = demo.test_cli_runner()
    ok = runner.invoke(args=["rebuild-learning-state"])
    assert ok.exit_code == 0 and "一致" in ok.output, ok.output

    conn = db.connect(db_config)
    with conn.cursor() as cur:
        cur.execute("UPDATE learning_state SET seen_count = seen_count + 5 ORDER BY id LIMIT 1")
        cur.execute("UPDATE learning_state SET next_review_at = NULL ORDER BY id DESC LIMIT 1")
    conn.commit()
    conn.close()
    drift = runner.invoke(args=["rebuild-learning-state"])
    assert drift.exit_code == 1 and "2 条不一致" in drift.output
    assert "seen_count" in drift.output and "next_review_at" in drift.output

    fixed = runner.invoke(args=["rebuild-learning-state", "--apply"])
    assert fixed.exit_code == 0 and "已按作答记录重建 2 条" in fixed.output
    assert runner.invoke(args=["rebuild-learning-state"]).exit_code == 0


def test_rebuild_limits_to_user_and_rejects_unknown_rule_version(demo, learner, db_config):
    _answer_mixed_history(demo, learner, db_config)
    runner = demo.test_cli_runner()
    assert runner.invoke(args=["rebuild-learning-state", "--username", "alice"]).exit_code == 0
    assert runner.invoke(args=["rebuild-learning-state", "--username", "nobody"]).exit_code != 0
    record_attempt(db_config, user_id(db_config), recognition_question(db_config, "notion")["id"], True, T0, rule="v0")
    failed = runner.invoke(args=["rebuild-learning-state"])
    assert failed.exit_code != 0 and "未知复习规则版本：v0" in failed.output


# 页面


def test_review_page_and_dashboard_show_progress(demo, learner, db_config):
    at(demo, T0)
    item = start(learner, "recognition", 1).get_json()["data"]["items"][0]
    answer(learner, item["id"], wrong(db_config, item["id"]))
    lemma = question_of(db_config, item["id"])["lemma_norm"]
    page = learner.get("/review").get_data(as_text=True)
    assert lemma in page and "10 分钟" in page
    dashboard = learner.get("/dashboard").get_data(as_text=True)
    assert "未测试" in dashboard and "104" in dashboard
    assert demo.test_client().get("/review").status_code == 302

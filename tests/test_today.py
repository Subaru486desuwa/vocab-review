"""今日任务（T15）：用户时区的当天、今日新词义、连续学习天数与完成状态。"""

from datetime import datetime, timedelta

import pytest

from tests.helpers import answer, login_as, query, question_of, right, select, start, wrong
from tests.test_progress import at, recognition_question, record_attempt, user_id

pytestmark = pytest.mark.db

T0 = datetime(2026, 11, 2, 8, 0, 0)  # 上海时间 11/02 16:00


def today(client):
    return client.get("/api/v1/me/today")


def new_sense_pool(config):
    """六级演示词表中有已发布辨义题的词义数。"""
    return query(
        config,
        "SELECT COUNT(DISTINCT s.id) AS n FROM wordbook_words m JOIN wordbooks b ON b.id = m.wordbook_id"
        " JOIN word_senses s ON s.word_id = m.word_id JOIN questions q ON q.sense_id = s.id"
        " AND q.skill_type = 'recognition' AND q.status = 'published' WHERE b.code = 'cet6-demo'",
    )[0]["n"]


def test_new_learner_has_ten_new_senses_and_no_streak(demo, learner, db_config):
    at(demo, T0)
    data = today(learner).get_json()["data"]
    assert (data["date"], data["timezone"]) == ("2026-11-02", "Asia/Shanghai")
    assert data["review"] == {"due": 0, "by_skill": {"recognition": 0, "spelling": 0, "context": 0}}
    assert data["new_senses"] == {"target": 10, "done": 0, "remaining": 10, "available": new_sense_pool(db_config)}
    assert data["streak"] == {"days": 0, "active_today": False}
    assert data["completed"] is False


def test_ten_new_senses_complete_the_day_until_a_wrong_answer_falls_due(demo, learner, db_config):
    at(demo, T0)
    session = start(learner, "recognition", 10, focus="new_senses").get_json()["data"]
    assert (session["focus"], session["total"]) == ("new_senses", 10)
    items = session["items"]
    answer(learner, items[0]["id"], wrong(db_config, items[0]["id"]))
    for item in items[1:]:
        answer(learner, item["id"], right(db_config, item["id"]))

    data = today(learner).get_json()["data"]
    assert data["new_senses"] == {
        "target": 10,
        "done": 10,
        "remaining": 0,
        "available": new_sense_pool(db_config) - 10,
    }
    assert data["streak"] == {"days": 1, "active_today": True}
    assert data["review"]["due"] == 0 and data["completed"] is True
    # 达成每日目标后仍可继续学新词义。
    html = learner.get("/today").get_data(as_text=True)
    assert "已达成目标 10 个" in html and 'data-focus="new_senses" data-count="10"' in html and "再学 10 个" in html

    at(demo, T0 + timedelta(minutes=11))
    data = today(learner).get_json()["data"]
    assert data["review"]["due"] == 1 and data["review"]["by_skill"]["recognition"] == 1
    assert data["completed"] is False


def test_new_sense_practice_skips_senses_answered_in_any_skill(demo, learner, db_config):
    at(demo, T0)
    spelled_item = start(learner, "spelling", 1).get_json()["data"]["items"][0]
    answer(learner, spelled_item["id"], "zzz")
    spelled = question_of(db_config, spelled_item["id"])["sense_id"]
    pool = new_sense_pool(db_config)
    assert today(learner).get_json()["data"]["new_senses"] == {
        "target": 10,
        "done": 1,
        "remaining": 9,
        "available": pool - 1,
    }

    issued = set()
    for _ in range(10):
        response = start(learner, "recognition", 20, focus="new_senses")
        if response.status_code != 201:
            break
        for item in response.get_json()["data"]["items"]:
            issued.add(question_of(db_config, item["id"])["sense_id"])
            answer(learner, item["id"], right(db_config, item["id"]))
    assert spelled not in issued and len(issued) == pool - 1
    assert (response.status_code, response.get_json()["error"]["code"]) == (422, "NO_QUESTIONS")
    data = today(learner).get_json()["data"]["new_senses"]
    assert (data["available"], data["remaining"]) == (0, 0)
    html = learner.get("/today").get_data(as_text=True)
    assert "都已练习过" in html and "再学" not in html


def test_focus_is_validated_and_today_requires_target(demo, db_config):
    client = login_as(demo, "bob")
    response = today(client)
    assert (response.status_code, response.get_json()["error"]["code"]) == (422, "NO_TARGET")
    select(client, db_config, "cet6-demo")
    response = start(client, "recognition", 5, focus="hard")
    assert response.status_code == 422 and "focus" in response.get_json()["error"]["fields"]


def test_day_follows_user_timezone_and_streak_counts_consecutive_days(demo, learner, db_config):
    uid = user_id(db_config)
    bank, fair = recognition_question(db_config, "bank"), recognition_question(db_config, "fair")
    record_attempt(db_config, uid, bank["id"], True, datetime(2026, 11, 2, 15, 30))  # 上海 11/02 23:30

    at(demo, datetime(2026, 11, 2, 16, 30))  # 上海 11/03 00:30：前一条作答属于昨天
    data = today(learner).get_json()["data"]
    assert data["date"] == "2026-11-03" and data["new_senses"]["done"] == 0
    assert data["streak"] == {"days": 1, "active_today": False}

    record_attempt(db_config, uid, fair["id"], False, datetime(2026, 11, 1, 2, 0))  # 上海 11/01 10:00
    record_attempt(db_config, uid, fair["id"], True, datetime(2026, 11, 2, 17, 0))  # 上海 11/03 01:00
    at(demo, datetime(2026, 11, 3, 3, 0))  # 上海 11/03 11:00
    data = today(learner).get_json()["data"]
    assert data["streak"] == {"days": 3, "active_today": True}
    assert data["new_senses"]["done"] == 0  # 两个词义的首次作答都早于今天

    other = login_as(demo, "bob")
    select(other, db_config, "cet6-demo")
    assert today(other).get_json()["data"]["streak"] == {"days": 0, "active_today": False}

    at(demo, datetime(2026, 11, 5, 3, 0))  # 上海 11/05：11/04 没有作答，连续中断
    assert today(learner).get_json()["data"]["streak"] == {"days": 0, "active_today": False}


def test_today_page_requires_login_and_links_from_dashboard(demo, learner, client):
    assert client.get("/today").status_code == 302
    at(demo, T0)
    html = learner.get("/today").get_data(as_text=True)
    assert "今日任务" in html and "0 / 10" in html and "连续学习" in html
    assert 'href="/today"' in learner.get("/dashboard").get_data(as_text=True)

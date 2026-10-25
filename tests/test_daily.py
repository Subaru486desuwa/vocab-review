"""学习趋势（T16）：按用户时区逐日汇总作答、新词义与复习，以及模拟演示数据生成。"""

from datetime import datetime, timedelta

import pytest

from app.repositories import db
from app.services import learning_state
from tests.helpers import PASSWORD, answer, login_as, query, question_of, right, select, start, wrong
from tests.test_progress import at, recognition_question, record_attempt, review, user_id

T0 = datetime(2026, 11, 2, 8, 0, 0)  # 上海时间 11/02 16:00
EMPTY_REVIEWS = {"due": 0, "due_correct": 0, "early": 0}


def daily(client, **params):
    return client.get("/api/v1/me/daily", query_string=params)


def day_of(data, date):
    return next(d for d in data["days"] if d["date"] == date)


def states_of(config, uid):
    return query(config, "SELECT * FROM learning_state WHERE user_id = %s ORDER BY id", (uid,))


def test_replay_steps_yield_state_before_each_attempt():
    def attempt(i, sense, correct, minute):
        return {
            "id": i,
            "user_id": 1,
            "sense_id": sense,
            "skill_type": "recognition",
            "is_correct": correct,
            "submitted_at": T0 + timedelta(minutes=minute),
            "review_rule_version": "review_rules_v1",
        }

    attempts = [attempt(1, 7, False, 0), attempt(2, 8, True, 1), attempt(3, 7, True, 12)]
    steps = list(learning_state.replay_steps(attempts))
    assert [s[0]["id"] for s in steps] == [1, 2, 3]
    assert steps[0][1] is None and steps[1][1] is None
    assert steps[2][1]["next_review_at"] == T0 + timedelta(minutes=10)
    assert steps[2][2]["seen_count"] == 2
    assert learning_state.replay(attempts) == {(1, 7, "recognition"): steps[2][2], (1, 8, "recognition"): steps[1][2]}


@pytest.mark.db
def test_days_follow_user_timezone_and_empty_days_are_zero(demo, learner, db_config):
    uid = user_id(db_config)
    bank = recognition_question(db_config, "bank")
    record_attempt(db_config, uid, bank["id"], True, datetime(2026, 11, 2, 15, 30))  # 上海 11/02 23:30
    record_attempt(db_config, uid, bank["id"], False, datetime(2026, 11, 2, 16, 30))  # 上海 11/03 00:30

    at(demo, datetime(2026, 11, 4, 4, 0))  # 上海 11/04 12:00
    data = daily(learner, days=3).get_json()["data"]
    assert data["timezone"] == "Asia/Shanghai"
    assert [d["date"] for d in data["days"]] == ["2026-11-02", "2026-11-03", "2026-11-04"]
    first, second, third = data["days"]
    assert first["attempts"] == {"count": 1, "correct": 1, "accuracy": 1.0}
    assert (first["new_senses"], first["first_on_skill"], first["reviews"]) == (1, 1, EMPTY_REVIEWS)
    # 第二次作答时还没到复习时间（答对后 1 天），计为提前练习。
    assert second["attempts"] == {"count": 1, "correct": 0, "accuracy": 0.0}
    assert (second["new_senses"], second["first_on_skill"]) == (0, 0)
    assert second["reviews"] == {"due": 0, "due_correct": 0, "early": 1}
    assert third["attempts"] == {"count": 0, "correct": 0, "accuracy": None}
    assert third["by_skill"]["spelling"] == {"count": 0, "correct": 0, "accuracy": None}
    assert (third["new_senses"], third["reviews"]) == (0, EMPTY_REVIEWS)
    # 11/02 日终错题尚未出现；11/03 00:30 答错，10 分钟后到期，之后一直待复习。
    assert [d["backlog_end"] for d in data["days"]] == [0, 1, 1]
    assert data["totals"]["attempts"] == {"count": 2, "correct": 1, "accuracy": 0.5}
    assert data["totals"]["active_days"] == 2


@pytest.mark.db
def test_attempts_split_into_first_due_and_early(demo, learner, db_config):
    at(demo, T0)
    first = start(learner, "recognition", 1).get_json()["data"]["items"][0]
    answer(learner, first["id"], wrong(db_config, first["id"]))
    sense = question_of(db_config, first["id"])["sense_id"]

    at(demo, T0 + timedelta(minutes=11))  # 错题已到期
    due = start(learner, "recognition", 1).get_json()["data"]["items"][0]
    assert question_of(db_config, due["id"])["sense_id"] == sense
    answer(learner, due["id"], wrong(db_config, due["id"]))

    at(demo, T0 + timedelta(minutes=15))  # 再次答错后 21 分才到期，此时练习是提前练习
    early = start(learner, "recognition", 1).get_json()["data"]["items"][0]
    assert question_of(db_config, early["id"])["sense_id"] == sense
    answer(learner, early["id"], right(db_config, early["id"]))

    spelling = query(
        db_config,
        "SELECT id FROM questions WHERE sense_id = %s AND skill_type = 'spelling' AND status = 'published' LIMIT 1",
        (sense,),
    )[0]
    record_attempt(db_config, user_id(db_config), spelling["id"], True, T0 + timedelta(minutes=20))

    at(demo, T0 + timedelta(minutes=30))
    row = day_of(daily(learner, days=1).get_json()["data"], "2026-11-02")
    assert row["attempts"] == {"count": 4, "correct": 2, "accuracy": 0.5}
    assert row["by_skill"]["recognition"]["count"] == 3 and row["by_skill"]["spelling"]["count"] == 1
    # 拼写是该词义在拼写题上的第一次作答，但不是新词义。
    assert (row["new_senses"], row["first_on_skill"]) == (1, 2)
    assert row["reviews"] == {"due": 1, "due_correct": 0, "early": 1}
    assert row["first_on_skill"] + row["reviews"]["due"] + row["reviews"]["early"] == row["attempts"]["count"]


@pytest.mark.db
def test_today_agrees_with_daily_plan_and_review_list_and_is_read_only(demo, learner, db_config):
    at(demo, T0)
    items = start(learner, "recognition", 10, focus="new_senses").get_json()["data"]["items"]
    for item in items[:2]:
        answer(learner, item["id"], wrong(db_config, item["id"]))
    for item in items[2:]:
        answer(learner, item["id"], right(db_config, item["id"]))
    other = login_as(demo, "bob")
    select(other, db_config, "cet6-demo")
    other_item = start(other, "recognition", 1).get_json()["data"]["items"][0]
    answer(other, other_item["id"], right(db_config, other_item["id"]))

    at(demo, T0 + timedelta(minutes=11))
    uid = user_id(db_config)
    before = states_of(db_config, uid)
    data = daily(learner).get_json()["data"]
    assert len(data["days"]) == 14 and data["days"][-1]["date"] == "2026-11-02"
    row = data["days"][-1]
    plan = learner.get("/api/v1/me/today").get_json()["data"]
    assert row["new_senses"] == plan["new_senses"]["done"] == 10
    assert row["backlog_end"] == len(review(learner).get_json()["data"]["due"]) == 2
    count = query(
        db_config,
        "SELECT COUNT(*) AS n FROM attempts a JOIN session_items i ON i.id = a.session_item_id"
        " JOIN practice_sessions p ON p.id = i.session_id WHERE p.user_id = %s",
        (uid,),
    )[0]["n"]
    assert data["totals"]["attempts"]["count"] == count == 10
    assert states_of(db_config, uid) == before
    with demo.app_context():
        assert learning_state.compare(db.get_db(), uid)[0] == []


@pytest.mark.db
def test_days_parameter_is_validated_and_login_is_required(demo, learner, client):
    at(demo, T0)
    for bad in ("0", "61", "abc", "1.5"):
        response = daily(learner, days=bad)
        assert response.status_code == 422 and "days" in response.get_json()["error"]["fields"]
    assert len(daily(learner, days=60).get_json()["data"]["days"]) == 60
    assert daily(client).status_code == 401
    assert client.get("/dashboard").status_code == 302


@pytest.mark.db
def test_dashboard_shows_last_fourteen_days(demo, learner, db_config):
    at(demo, T0)
    item = start(learner, "recognition", 1).get_json()["data"]["items"][0]
    answer(learner, item["id"], right(db_config, item["id"]))
    html = learner.get("/dashboard").get_data(as_text=True)
    assert "近 14 天" in html and html.count('class="trend-row"') == 14
    assert "11-02" in html and "10-20" in html and "日终待复习" in html


def seed(app, username, days="7", seed_value="42"):
    return app.test_cli_runner().invoke(
        args=["seed-demo-history", "--username", username, "--days", days, "--seed", seed_value]
    )


def per_day(config, uid):
    rows = query(
        config,
        "SELECT DATE(CONVERT_TZ(a.submitted_at, '+00:00', '+08:00')) AS d, COUNT(*) AS n, SUM(a.is_correct) AS c"
        " FROM attempts a JOIN session_items i ON i.id = a.session_item_id"
        " JOIN practice_sessions p ON p.id = i.session_id WHERE p.user_id = %s GROUP BY d ORDER BY d",
        (uid,),
    )
    return [(r["d"].isoformat(), r["n"], int(r["c"])) for r in rows]


@pytest.mark.db
def test_seed_demo_history_simulates_days_through_real_services(demo, db_config, monkeypatch):
    monkeypatch.setenv("DEMO_USER_PASSWORD", PASSWORD)
    at(demo, datetime(2026, 11, 20, 4, 0))  # 上海 11/20 12:00
    result = seed(demo, "sim_trend")
    assert result.exit_code == 0, result.output
    assert "模拟演示数据" in result.output

    uid = user_id(db_config, "sim_trend")
    days = per_day(db_config, uid)
    dates = [d for d, _, _ in days]
    assert dates and dates[0] >= "2026-11-13" and dates[-1] <= "2026-11-19"  # 只生成今天之前的 7 天
    assert len(dates) >= 4
    with demo.app_context():
        assert learning_state.compare(db.get_db(), uid)[0] == []

    client = demo.test_client()
    assert client.post("/auth/login", data={"username": "sim_trend", "password": PASSWORD}).status_code == 302
    data = daily(client, days=8).get_json()["data"]
    assert data["totals"]["attempts"]["count"] == sum(n for _, n, _ in days)
    assert data["totals"]["reviews"]["due"] > 0 and data["totals"]["new_senses"] > 0
    assert data["days"][-1]["attempts"]["count"] == 0  # 今天留给现场练习

    again = seed(demo, "sim_trend")
    assert again.exit_code != 0 and "已有作答" in again.output
    plain = seed(demo, "trend_user")
    assert plain.exit_code != 0 and "sim_" in plain.output

    # 同一种子在全新账户上生成相同的逐日结果。
    assert seed(demo, "sim_copy").exit_code == 0
    assert per_day(db_config, user_id(db_config, "sim_copy")) == days

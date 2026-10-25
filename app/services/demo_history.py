"""模拟演示数据：在固定时钟下调用真实组卷与作答服务，逐日生成作答，供学习趋势演示。

账户名必须以 sim_ 开头；生成的作答不是真实学习记录，证据与报告须如实标注。
"""

import json
import random
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.repositories import db, users
from app.repositories import practice as practice_repo
from app.repositories import progress as progress_repo
from app.services import grading, practice
from app.services.content_import import SKILL_TYPES
from app.services.today import local_day

PREFIX = "sim_"
REST_RATE = 0.2  # 某天不练习的概率；最近一天总会练习
START_HOUR = 20  # 每天开始练习的本地时刻
NEW_CORRECT = 0.7
REVIEW_CORRECT = 0.85
EXTRA_CORRECT = 0.75  # 拼写或语境自由练习
EXTRA_COUNT = 5
RETRY_AFTER = timedelta(minutes=15)  # 错题 10 分钟后到期，稍后再复习一轮


class HasHistory(Exception):
    pass


class _Clock:
    """模拟一天里的练习时间；每作答一题前进若干秒。"""

    def __init__(self, start, rng):
        self.now, self.rng, self.answered = start, rng, 0

    def tick(self):
        self.now += timedelta(seconds=self.rng.randint(8, 40))
        return self.now


def has_history(conn, user_id):
    with db.transaction(conn):
        return bool(progress_repo.attempt_times(conn, user_id))


def _answer(conn, item_id, correct, rng):
    with db.transaction(conn):
        row = practice_repo.item_with_question(conn, item_id)
    question = {
        "skill_type": row["skill_type"],
        "options": json.loads(row["options_json"]) if row["options_json"] else None,
        "answers": json.loads(row["answers_json"]),
    }
    right = grading.correct_answer(question)
    if question["skill_type"] == "spelling":
        return right["text"] if correct else right["text"][:-1] or "?"
    if correct:
        return right["option_id"]
    return rng.choice([o["id"] for o in question["options"] if o["id"] != right["option_id"]])


def _session(conn, user_id, skill, count, clock, rng, p_correct, focus=None):
    try:
        session = practice.create_session(conn, user_id, skill, count, None, clock.now, rng=rng, focus=focus)
    except practice.NoQuestions:
        return
    for item in session["items"]:
        value = _answer(conn, item["id"], rng.random() < p_correct, rng)
        at = clock.tick()
        practice.submit_answer(conn, user_id, item["id"], value, lambda at=at: at)
        clock.answered += 1


def _review(conn, user_id, clock, rng):
    with db.transaction(conn):
        states = progress_repo.all_learning_states(conn, user_id)
    for skill in SKILL_TYPES:
        due = sum(1 for s in states if s["skill_type"] == skill and s["next_review_at"] <= clock.now)
        if due:
            _session(conn, user_id, skill, min(due, practice.MAX_COUNT), clock, rng, REVIEW_CORRECT)


def generate(conn, user_id, now, days, seed):
    """为 now 所在本地日之前的 days 天逐日练习：先复习到期内容，再学新词义、做一组拼写或语境，稍后复习错题。

    返回 [(日期, 作答数)]。用户已有作答时拒绝，避免与真实或既有记录混在一起。
    """
    if has_history(conn, user_id):
        raise HasHistory
    rng = random.Random(seed)
    with db.transaction(conn):
        user = users.find_by_id(conn, user_id)
    tz = ZoneInfo(user["display_timezone"])
    today, _, _ = local_day(now, tz)
    result = []
    for offset in range(days, 0, -1):
        day = today - timedelta(days=offset)
        if offset > 1 and rng.random() < REST_RATE:
            result.append((day, 0))
            continue
        start = datetime.combine(day, time(START_HOUR, rng.randrange(60)), tzinfo=tz)
        clock = _Clock(start.astimezone(UTC).replace(tzinfo=None), rng)
        _review(conn, user_id, clock, rng)
        _session(conn, user_id, "recognition", practice.DEFAULT_COUNT, clock, rng, NEW_CORRECT, focus="new_senses")
        _session(conn, user_id, rng.choice(("spelling", "context")), EXTRA_COUNT, clock, rng, EXTRA_CORRECT)
        clock.now += RETRY_AFTER
        _review(conn, user_id, clock, rng)
        result.append((day, clock.answered))
    return result

"""学习趋势：按用户时区逐日汇总作答、新词义与复习，全部由作答事实重放计算，只读。"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.repositories import db, users
from app.repositories import progress as repo
from app.services import learning_state
from app.services.content_import import SKILL_TYPES
from app.services.practice import InvalidRequest
from app.services.today import local_day

DEFAULT_DAYS = 14
MAX_DAYS = 60
GRANULARITY = (
    "按用户时区的自然日统计该用户的全部作答，不按目标词表过滤；每次作答按作答前学习状态归入"
    "首次作答该题型、到期复习或提前练习之一；日终待复习为当天结束时（今天为当前时间）已到复习时间的词义 × 题型数。"
)


def _counts():
    return {"count": 0, "correct": 0}


def _with_accuracy(counts):
    count, correct = counts["count"], counts["correct"]
    return {"count": count, "correct": correct, "accuracy": round(correct / count, 4) if count else None}


def _empty_row(day):
    return {
        "date": day.isoformat(),
        "attempts": _counts(),
        "by_skill": {skill: _counts() for skill in SKILL_TYPES},
        "new_senses": 0,
        "first_on_skill": 0,
        "reviews": {"due": 0, "due_correct": 0, "early": 0},
        "backlog_end": 0,
    }


def _day_end(day, tz):
    return datetime.combine(day + timedelta(days=1), time(), tzinfo=tz).astimezone(UTC).replace(tzinfo=None)


def trend(conn, user_id, now, days=DEFAULT_DAYS):
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
        raise InvalidRequest({"days": f"days 必须是 1—{MAX_DAYS} 的整数"})
    with db.transaction(conn):
        user = users.find_by_id(conn, user_id)
        attempts = [a for a in repo.all_attempts(conn, user_id) if a["submitted_at"] <= now]
    tz = ZoneInfo(user["display_timezone"])
    today, _, _ = local_day(now, tz)
    dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    rows = {day: _empty_row(day) for day in dates}
    # 过去各天的日终边界按时间顺序在重放途中结算；今天的边界是当前时间，重放结束后结算。
    boundaries = [(day, _day_end(day, tz)) for day in dates[:-1]]
    states, seen_senses = {}, set()

    def settle(until):
        while boundaries and boundaries[0][1] <= until:
            day, end = boundaries.pop(0)
            rows[day]["backlog_end"] = sum(1 for s in states.values() if s["next_review_at"] <= end)

    for attempt, before, after in learning_state.replay_steps(attempts):
        submitted_at = attempt["submitted_at"]
        settle(submitted_at)
        states[(attempt["sense_id"], attempt["skill_type"])] = after
        is_new = attempt["sense_id"] not in seen_senses
        seen_senses.add(attempt["sense_id"])
        row = rows.get(submitted_at.replace(tzinfo=UTC).astimezone(tz).date())
        if row is None:
            continue
        correct = int(bool(attempt["is_correct"]))
        for counts in (row["attempts"], row["by_skill"][attempt["skill_type"]]):
            counts["count"] += 1
            counts["correct"] += correct
        row["new_senses"] += is_new
        if before is None:
            row["first_on_skill"] += 1
        elif before["next_review_at"] <= submitted_at:
            row["reviews"]["due"] += 1
            row["reviews"]["due_correct"] += correct
        else:
            row["reviews"]["early"] += 1
    settle(now)
    rows[today]["backlog_end"] = sum(1 for s in states.values() if s["next_review_at"] <= now)

    ordered = [rows[day] for day in dates]
    for row in ordered:
        row["attempts"] = _with_accuracy(row["attempts"])
        row["by_skill"] = {skill: _with_accuracy(c) for skill, c in row["by_skill"].items()}
    total = {
        "count": sum(r["attempts"]["count"] for r in ordered),
        "correct": sum(r["attempts"]["correct"] for r in ordered),
    }
    return {
        "timezone": user["display_timezone"],
        "granularity": GRANULARITY,
        "days": ordered,
        "totals": {
            "attempts": _with_accuracy(total),
            "new_senses": sum(r["new_senses"] for r in ordered),
            "first_on_skill": sum(r["first_on_skill"] for r in ordered),
            "reviews": {k: sum(r["reviews"][k] for r in ordered) for k in ("due", "due_correct", "early")},
            "active_days": sum(1 for r in ordered if r["attempts"]["count"]),
        },
    }

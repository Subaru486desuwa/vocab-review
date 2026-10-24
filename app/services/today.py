"""今日任务：按用户时区的当天汇总待复习、今日新词义与连续学习天数，全部由作答事实与学习状态计算。"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.repositories import db, users
from app.repositories import practice as practice_repo
from app.repositories import progress as repo
from app.repositories import wordbooks as wordbook_repo
from app.services import progress
from app.services.content_import import SKILL_TYPES
from app.services.practice import NoTarget

DAILY_NEW_SENSES = 10
NEW_SENSE_SKILL = "recognition"


def local_day(now, tz):
    """now（UTC，无时区）所在的本地日期，以及该日起止对应的 UTC 时间。"""
    day = now.replace(tzinfo=UTC).astimezone(tz).date()
    start = datetime.combine(day, time(), tzinfo=tz).astimezone(UTC).replace(tzinfo=None)
    end = datetime.combine(day + timedelta(days=1), time(), tzinfo=tz).astimezone(UTC).replace(tzinfo=None)
    return day, start, end


def streak(times, today, tz):
    """截至今天（今天无作答时截至昨天）连续有作答的天数。"""
    days = {t.replace(tzinfo=UTC).astimezone(tz).date() for t in times}
    active = today in days
    day, count = (today if active else today - timedelta(days=1)), 0
    while day in days:
        count, day = count + 1, day - timedelta(days=1)
    return {"days": count, "active_today": active}


def plan(conn, user_id, now):
    review = progress.review_list(conn, user_id, now)
    with db.transaction(conn):
        user = users.find_by_id(conn, user_id)
        books = wordbook_repo.selected(conn, user_id)
        if not books:
            raise NoTarget
        candidates = practice_repo.candidate_senses(conn, [b["id"] for b in books], NEW_SENSE_SKILL)
        first = repo.first_attempts(conn, user_id)
        times = repo.attempt_times(conn, user_id)
    tz = ZoneInfo(user["display_timezone"])
    day, start, end = local_day(now, tz)
    by_skill = {skill: sum(1 for e in review["due"] if e["skill_type"] == skill) for skill in SKILL_TYPES}
    done = sum(1 for first_at in first.values() if start <= first_at < end)
    available = sum(1 for sense_id in candidates if sense_id not in first)
    remaining = min(max(DAILY_NEW_SENSES - done, 0), available)
    due = len(review["due"])
    return {
        "date": day.isoformat(),
        "timezone": user["display_timezone"],
        "review": {"due": due, "by_skill": by_skill},
        "new_senses": {"target": DAILY_NEW_SENSES, "done": done, "remaining": remaining, "available": available},
        "streak": streak(times, day, tz),
        "completed": due == 0 and remaining == 0,
    }

"""从作答事实重建学习状态投影，并与当前 learning_state 比对。

按 (submitted_at, attempt_id) 顺序、使用每条作答记录保存的复习规则版本重放。
"""

from app.repositories import db
from app.repositories import progress as repo
from app.services import review_rules

RULES = review_rules.RULES
FIELDS = ("seen_count", "correct_count", "correct_streak", "interval_stage", "last_attempt_at", "next_review_at")


class UnknownRuleVersion(Exception):
    pass


def replay_steps(attempts):
    """逐条产出 (作答, 作答前状态, 作答后状态)；该 (用户, 词义, 题型) 首次作答时作答前状态为 None。"""
    states = {}
    for attempt in attempts:
        rule = RULES.get(attempt["review_rule_version"])
        if rule is None:
            raise UnknownRuleVersion(attempt["review_rule_version"])
        key = (attempt["user_id"], attempt["sense_id"], attempt["skill_type"])
        before = states.get(key)
        states[key] = rule(before or review_rules.initial(), bool(attempt["is_correct"]), attempt["submitted_at"])
        yield attempt, before, states[key]


def replay(attempts):
    return {(a["user_id"], a["sense_id"], a["skill_type"]): after for a, _, after in replay_steps(attempts)}


def _differences(stored_rows, attempts):
    rebuilt = replay(attempts)
    stored = {(r["user_id"], r["sense_id"], r["skill_type"]): r for r in stored_rows}
    initial = review_rules.initial()
    diffs = []
    for key in sorted(set(stored) | set(rebuilt)):
        old, new = stored.get(key, initial), rebuilt.get(key, initial)
        changed = {field: (old[field], new[field]) for field in FIELDS if old[field] != new[field]}
        if changed:
            diffs.append({"key": key, "changed": changed, "rebuilt": new})
    return diffs, len(set(stored) | set(rebuilt))


def compare(conn, user_id=None):
    """返回 (不一致列表, 核对的组合数)；不修改数据。"""
    with db.transaction(conn):
        return _differences(repo.all_learning_states(conn, user_id), repo.all_attempts(conn, user_id))


def rebuild(conn, user_id=None):
    """把不一致的学习状态改写为重放结果，返回改写条数。应在没有练习进行时执行。"""
    with db.transaction(conn):
        stored = repo.all_learning_states(conn, user_id, lock=True)
        diffs, _ = _differences(stored, repo.all_attempts(conn, user_id))
        for diff in diffs:
            repo.upsert_learning_state(conn, *diff["key"], diff["rebuilt"])
    return diffs

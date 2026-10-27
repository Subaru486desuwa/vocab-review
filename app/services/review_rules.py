"""可解释的复习安排，规则见 docs/data-model.md。

纯函数，不读写数据库；作答事务按当前版本 VERSION 调用，重建时按作答记录保存的版本重放（见 RULES）。
v1：答错 10 分钟后复习，答对按 1/3/7/14 天推进。
v2：在 v1 基础上，未到复习时间的提前练习答对只累计次数，不推进间隔、不改复习时间（错题恢复除外）。
"""

from datetime import timedelta

V1 = "review_rules_v1"
V2 = "review_rules_v2"
VERSION = V2
INTERVAL_DAYS = (1, 3, 7, 14)
MAX_STAGE = len(INTERVAL_DAYS) - 1
RETRY_AFTER_WRONG = timedelta(minutes=10)


def initial():
    return {
        "seen_count": 0,
        "correct_count": 0,
        "correct_streak": 0,
        "interval_stage": 0,
        "last_attempt_at": None,
        "next_review_at": None,
    }


def apply_v1(state, is_correct, submitted_at):
    """返回作答后的新学习状态，不修改 state。"""
    new = {**state, "seen_count": state["seen_count"] + 1, "last_attempt_at": submitted_at}
    if is_correct:
        stage = state["interval_stage"]
        new["correct_count"] = state["correct_count"] + 1
        new["correct_streak"] = state["correct_streak"] + 1
        new["next_review_at"] = submitted_at + timedelta(days=INTERVAL_DAYS[stage])
        new["interval_stage"] = min(stage + 1, MAX_STAGE)
    else:
        new["correct_streak"] = 0
        new["interval_stage"] = 0
        new["next_review_at"] = submitted_at + RETRY_AFTER_WRONG
    return new


def apply_v2(state, is_correct, submitted_at):
    early = (
        is_correct
        and state["correct_streak"] > 0
        and state["next_review_at"] is not None
        and submitted_at < state["next_review_at"]
    )
    if not early:
        return apply_v1(state, is_correct, submitted_at)
    return {
        **state,
        "seen_count": state["seen_count"] + 1,
        "correct_count": state["correct_count"] + 1,
        "correct_streak": state["correct_streak"] + 1,
        "last_attempt_at": submitted_at,
    }


RULES = {V1: apply_v1, V2: apply_v2}
apply = RULES[VERSION]

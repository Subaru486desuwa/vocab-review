"""review_rules_v1：可解释的复习安排，规则见 docs/data-model.md。

纯函数，不读写数据库；作答事务按作答记录保存的版本调用，重建时按同一规则重放。
"""

from datetime import timedelta

VERSION = "review_rules_v1"
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


def apply(state, is_correct, submitted_at):
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

"""当前证据（evidence_v1）：按 词义 × 题型 汇总作答事实，估计记忆强度并判定当前状态。

纯函数，不读写数据库；诊断页、今日任务、复习计划与选题决策共用同一口径。
记忆强度采用半衰期回归（Settles & Meeder 2016，Duolingo）的形式：p = 2^(-Δ/h)，h = 2^(θ·x) 天，
x = (1, √(1+正确次数), √(1+错误次数))。θ 为手工设定的固定值，不在本系统数据上训练，
只用于排序与解释，不是掌握度，也不改变复习安排。
"""

import math

VERSION = "evidence_v1"
THETA = (-1.8, 2.0, -1.0)
RECENT = 5
WEAK_WINDOW = 3
FADING_BELOW = 0.5
STRENGTH_LEVELS = (0.5, 0.7, 0.9)
STATUSES = ("weak", "fading", "improved", "stable")


def half_life_days(correct, wrong):
    bias, right_w, wrong_w = THETA
    return 2 ** (bias + right_w * math.sqrt(1 + correct) + wrong_w * math.sqrt(1 + wrong))


def recall(correct, wrong, days_since):
    return 2 ** (-max(days_since, 0.0) / half_life_days(correct, wrong))


def strength(p):
    """1—4 格：<0.5、0.5—0.7、0.7—0.9、≥0.9。"""
    return 1 + sum(1 for level in STRENGTH_LEVELS if p >= level)


def status(history, p):
    """history 为按时间排序的正误列表。

    weak：最近一次答错，或最近 3 次至少错 2 次；fading：不属 weak 且记忆强度 < 0.5；
    improved：曾答错、最近 3 次全对；其余 stable。
    """
    last = history[-WEAK_WINDOW:]
    if not history[-1] or last.count(False) >= 2:
        return "weak"
    if p < FADING_BELOW:
        return "fading"
    if False in history and len(last) == WEAK_WINDOW and all(last):
        return "improved"
    return "stable"


def items(attempts, now):
    """attempts 为含 sense_id、skill_type、is_correct、submitted_at 的作答，按 (submitted_at, id) 排序。

    返回 (sense_id, skill_type) → 证据；未作答的组合不出现（未测试不赋分数）。
    """
    histories = {}
    for a in attempts:
        histories.setdefault((a["sense_id"], a["skill_type"]), []).append(a)
    result = {}
    for key, rows in histories.items():
        history = [bool(r["is_correct"]) for r in rows]
        correct = sum(history)
        wrong = len(history) - correct
        last_at = rows[-1]["submitted_at"]
        days = max((now - last_at).total_seconds(), 0.0) / 86400
        p = recall(correct, wrong, days)
        recent = history[-RECENT:]
        result[key] = {
            "sense_id": key[0],
            "skill_type": key[1],
            "seen": len(history),
            "correct": correct,
            "wrong": wrong,
            "recent": recent,
            "recent_wrong": recent.count(False),
            "last_attempt_at": last_at,
            "days_since": round(days, 2),
            "half_life_days": round(half_life_days(correct, wrong), 2),
            "recall": round(p, 4),
            "strength": strength(p),
            "status": status(history, p),
        }
    return result


def weak_order(item):
    """当前弱项的排序键：近期错误比例高、半衰期短、最近答错的在前。

    刚作答的项距上次接近 0 天、记忆强度都接近 1，因此弱项之间按半衰期而不是记忆强度比较。
    """
    error_rate = item["recent_wrong"] / len(item["recent"])
    return (-error_rate, item["half_life_days"], -item["last_attempt_at"].timestamp(), item["sense_id"])


def fading_order(item):
    return (item["recall"], item["sense_id"])

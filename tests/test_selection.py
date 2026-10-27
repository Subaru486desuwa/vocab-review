"""当前证据（evidence_v1）与选题决策（selection_v1）的纯函数测试，不连接数据库。"""

import random
from datetime import datetime, timedelta

from app.services import evidence, selection

NOW = datetime(2026, 10, 27, 8, 0, 0)


def attempts(sense_id, results, start, skill="recognition", step=timedelta(hours=1)):
    return [
        {"sense_id": sense_id, "skill_type": skill, "is_correct": ok, "submitted_at": start + i * step}
        for i, ok in enumerate(results)
    ]


def test_half_life_grows_with_correct_and_shrinks_with_wrong():
    assert evidence.half_life_days(4, 0) > evidence.half_life_days(1, 0) > evidence.half_life_days(1, 3)
    assert evidence.recall(1, 0, 0) == 1.0
    assert abs(evidence.recall(1, 0, evidence.half_life_days(1, 0)) - 0.5) < 1e-9
    assert [evidence.strength(p) for p in (0.1, 0.5, 0.7, 0.95)] == [1, 2, 3, 4]


def test_recent_errors_outrank_old_errors_that_improved():
    # 报告探针：先错 5 次再对 20 次，不应排在最近 2 次全错之前。
    old = attempts(1, [False] * 5 + [True] * 20, NOW - timedelta(days=3))
    recent = attempts(2, [False, False], NOW - timedelta(hours=3))
    found = evidence.items(sorted(old + recent, key=lambda a: a["submitted_at"]), NOW)
    old_item, recent_item = found[(1, "recognition")], found[(2, "recognition")]
    assert old_item["status"] == "improved" and recent_item["status"] == "weak"
    assert recent_item["recall"] < old_item["recall"]
    plan = selection.weak([1, 2], {1: old_item, 2: recent_item}, 10)
    assert [s for s, _ in plan] == [2]


def test_status_rules():
    def status_of(results, days_ago=0.0):
        rows = attempts(7, results, NOW - timedelta(days=days_ago, hours=len(results)))
        return evidence.items(rows, NOW)[(7, "recognition")]["status"]

    assert status_of([True, True, False]) == "weak"
    assert status_of([True, False, False, True]) == "weak"
    assert status_of([False, True, False, True]) == "stable"
    assert status_of([False, True, True, True]) == "improved"
    assert status_of([True, True]) == "stable"
    assert status_of([True], days_ago=3) == "fading"


def test_skills_are_separate_evidence():
    rows = attempts(3, [True, True, True], NOW - timedelta(days=1)) + attempts(
        3, [False], NOW - timedelta(hours=1), skill="spelling"
    )
    found = evidence.items(rows, NOW)
    assert found[(3, "recognition")]["status"] == "stable" and found[(3, "spelling")]["status"] == "weak"


def test_due_items_are_ordered_by_recall_not_by_random_seed():
    # 报告探针：两个都到期的词义，换种子不应改变顺序；记忆强度低的先出。
    fresh = attempts(10, [True], NOW - timedelta(days=1, minutes=1))
    long_overdue = attempts(11, [True], NOW - timedelta(days=5))
    found = {k[0]: v for k, v in evidence.items(fresh + long_overdue, NOW).items()}
    states = {
        10: {"seen_count": 1, "correct_streak": 1, "next_review_at": NOW - timedelta(minutes=1)},
        11: {"seen_count": 1, "correct_streak": 1, "next_review_at": NOW - timedelta(days=4)},
        12: {"seen_count": 1, "correct_streak": 0, "next_review_at": NOW + timedelta(minutes=5)},
    }
    for seed in range(5):
        plan = selection.default([10, 11, 12, 13], states, found, NOW, 4, random.Random(seed))
        assert [s for s, _ in plan] == [11, 10, 12, 13]
        assert [r["code"] for _, r in plan] == ["due", "due", "wrong_pending", "untested"]
    assert plan[0][1]["recall"] < plan[1][1]["recall"] and "recall" not in plan[3][1]


def test_weak_focus_puts_weak_before_fading_and_skips_stable():
    rows = (
        attempts(20, [True], NOW - timedelta(days=4))  # fading
        + attempts(21, [True, False], NOW - timedelta(hours=5))  # weak 1/2
        + attempts(22, [False, False, False], NOW - timedelta(hours=8))  # weak 3/3
        + attempts(23, [True, True, True], NOW - timedelta(hours=4))  # stable
    )
    found = {k[0]: v for k, v in evidence.items(rows, NOW).items()}
    plan = selection.weak([20, 21, 22, 23, 24], found, 10)
    assert [(s, r["code"]) for s, r in plan] == [(22, "weak"), (21, "weak"), (20, "fading")]
    assert plan[0][1]["recent_wrong"] == 3 and plan[0][1]["recent_count"] == 3
    assert selection.weak([20, 21, 22], found, 1) == plan[:1]


def test_targeted_keeps_requested_order_and_skips_unavailable():
    plan = selection.targeted([1, 2, 3], [3, 9, 1, 3], {}, 10)
    assert plan == [(3, {"code": "targeted"}), (1, {"code": "targeted"})]
    assert selection.targeted([1, 2, 3], [9], {}, 10) == []


def test_weak_items_with_equal_error_rate_rank_by_half_life_not_fresh_recall():
    # 刚答错的两项记忆强度都接近 1；答对次数少的半衰期更短，应先出。
    pattern = [False, True, True, True, False]
    rows = attempts(30, [True] * 8 + pattern, NOW - timedelta(hours=14)) + attempts(
        31, pattern, NOW - timedelta(hours=6)
    )
    found = {k[0]: v for k, v in evidence.items(sorted(rows, key=lambda a: a["submitted_at"]), NOW).items()}
    assert found[30]["recent"] == found[31]["recent"] == pattern
    assert found[30]["status"] == found[31]["status"] == "weak"
    assert found[31]["half_life_days"] < found[30]["half_life_days"]
    assert [s for s, _ in selection.weak([30, 31], found, 10)] == [31, 30]

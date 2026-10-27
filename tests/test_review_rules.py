from datetime import datetime, timedelta

from app.services import review_rules

T0 = datetime(2026, 10, 24, 8, 0, 0)


def test_version_is_recorded():
    assert review_rules.VERSION == "review_rules_v2"
    assert set(review_rules.RULES) == {"review_rules_v1", "review_rules_v2"}


def test_wrong_answer_resets_and_reviews_in_ten_minutes():
    state = {**review_rules.initial(), "seen_count": 3, "correct_count": 3, "correct_streak": 3, "interval_stage": 3}
    new = review_rules.apply(state, False, T0)
    assert (new["seen_count"], new["correct_count"], new["correct_streak"], new["interval_stage"]) == (4, 3, 0, 0)
    assert new["next_review_at"] == T0 + timedelta(minutes=10)
    assert new["last_attempt_at"] == T0


def test_correct_answers_follow_1_3_7_14_days_and_cap_stage():
    state, t, gaps = review_rules.initial(), T0, []
    for _ in range(5):
        state = review_rules.apply(state, True, t)
        gaps.append((state["next_review_at"] - t).days)
        t = state["next_review_at"]
    assert gaps == [1, 3, 7, 14, 14]
    assert (state["interval_stage"], state["correct_streak"], state["correct_count"]) == (3, 5, 5)


def test_apply_does_not_mutate_input():
    state = review_rules.initial()
    review_rules.apply(state, True, T0)
    assert state == review_rules.initial()


def test_v2_early_correct_practice_does_not_advance_interval():
    # 报告探针：3 秒内连续答对 4 次。v1 推进到阶段 3、14 天后复习；v2 只第一次推进。
    v1, v2 = review_rules.initial(), review_rules.initial()
    for second in range(4):
        v1 = review_rules.apply_v1(v1, True, T0 + timedelta(seconds=second))
        v2 = review_rules.apply_v2(v2, True, T0 + timedelta(seconds=second))
    assert (v1["interval_stage"], v1["next_review_at"]) == (3, T0 + timedelta(seconds=3, days=14))
    assert (v2["interval_stage"], v2["next_review_at"]) == (1, T0 + timedelta(days=1))
    assert (v2["seen_count"], v2["correct_count"], v2["correct_streak"]) == (4, 4, 4)
    assert v2["last_attempt_at"] == T0 + timedelta(seconds=3)


def test_v2_matches_v1_when_due_wrong_or_recovering():
    state = review_rules.initial()
    t = T0
    for _ in range(5):
        state = review_rules.apply_v2(state, True, t)
        t = state["next_review_at"]
    assert state["interval_stage"] == 3
    wrong = review_rules.apply_v2(state, False, T0 + timedelta(days=2))
    assert wrong == review_rules.apply_v1(state, False, T0 + timedelta(days=2))
    # 错题未到 10 分钟就答对：仍按 v1 恢复为 1 天后复习。
    recovered = review_rules.apply_v2(wrong, True, T0 + timedelta(days=2, minutes=1))
    assert recovered == review_rules.apply_v1(wrong, True, T0 + timedelta(days=2, minutes=1))

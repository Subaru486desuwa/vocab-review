from datetime import datetime, timedelta

from app.services import review_rules

T0 = datetime(2026, 10, 24, 8, 0, 0)


def test_version_is_recorded():
    assert review_rules.VERSION == "review_rules_v1"


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

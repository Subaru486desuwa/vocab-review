import pytest

from app.services import grading

CHOICE = {
    "skill_type": "recognition",
    "options": [{"id": "a", "text": "银行"}, {"id": "b", "text": "河岸"}],
    "answers": {"option_id": "b"},
    "grading_policy": {"type": "choice"},
}
SPELLING = {
    "skill_type": "spelling",
    "options": None,
    "answers": {"accepted": ["analyse", "analyze"]},
    "grading_policy": {"type": "text", "trim": True, "case_sensitive": False},
}


@pytest.mark.parametrize(
    ("question", "raw", "expected"),
    [
        (CHOICE, "b", (True, None)),
        (CHOICE, "a", (False, "meaning")),
        (CHOICE, "", (False, "unanswered")),
        ({**CHOICE, "skill_type": "context"}, "a", (False, "context")),
        (SPELLING, " Analyse ", (True, None)),
        (SPELLING, "analyze", (True, None)),
        (SPELLING, "analise", (False, "spelling")),
        (SPELLING, "   ", (False, "unanswered")),
    ],
)
def test_grade(question, raw, expected):
    assert grading.grade(question, grading.normalize(question, raw)) == expected


def test_normalized_answer_follows_policy():
    assert grading.normalize(SPELLING, "  AnalYse ") == "analyse"
    strict = {**SPELLING, "grading_policy": {"type": "text", "trim": False, "case_sensitive": True}}
    assert grading.normalize(strict, " Analyse") == " Analyse"
    assert grading.grade(strict, grading.normalize(strict, " analyse")) == (False, "spelling")
    assert grading.normalize(CHOICE, " b ") == "b"


@pytest.mark.parametrize(("question", "raw"), [(CHOICE, "z"), (CHOICE, 3), (SPELLING, "x" * 256), (SPELLING, None)])
def test_malformed_answers_are_rejected(question, raw):
    with pytest.raises(grading.InvalidAnswer):
        grading.normalize(question, raw)


def test_correct_answer_for_display():
    assert grading.correct_answer(CHOICE) == {"option_id": "b", "text": "河岸"}
    assert grading.correct_answer(SPELLING) == {"text": "analyse", "accepted": ["analyse", "analyze"]}

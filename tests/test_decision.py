"""T18：诊断到练习的决策闭环——定向练习、弱项专练、选题理由与改善后的诊断反馈。"""

import json

import pytest

from app.repositories import db
from app.services import learning_state
from tests.helpers import answer, query, question_of, right, start, wrong

pytestmark = pytest.mark.db


def senses_of(config, code, skill="recognition"):
    return [
        r["id"]
        for r in query(
            config,
            "SELECT DISTINCT s.id FROM word_senses s JOIN wordbook_words m ON m.word_id = s.word_id"
            " JOIN wordbooks b ON b.id = m.wordbook_id JOIN questions q ON q.sense_id = s.id"
            " WHERE b.code = %s AND q.skill_type = %s AND q.status = 'published' ORDER BY s.id",
            (code, skill),
        )
    ]


def targeted(client, sense_id, skill="recognition"):
    response = start(client, skill, 5, sense_ids=[sense_id])
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def practice_once(client, config, sense_id, correct):
    [item] = targeted(client, sense_id)["items"]
    value = right(config, item["id"]) if correct else wrong(config, item["id"])
    assert answer(client, item["id"], value).status_code == 200


def current(client):
    response = client.get("/api/v1/me/insights")
    assert response.status_code == 200
    return response.get_json()["data"]["current"]


def test_targeted_session_covers_requested_senses_with_reason(learner, db_config):
    first, second = senses_of(db_config, "cet6-demo")[:2]
    session = start(learner, "recognition", 5, sense_ids=[second, first, second]).get_json()["data"]
    assert [question_of(db_config, i["id"])["sense_id"] for i in session["items"]] == [second, first]
    assert [i["reason"] for i in session["items"]] == [{"code": "targeted"}] * 2
    snapshot = json.loads(
        query(db_config, "SELECT target_snapshot_json FROM practice_sessions")[0]["target_snapshot_json"]
    )
    assert (snapshot["selection_version"], snapshot["evidence_version"]) == ("selection_v1", "evidence_v1")
    assert snapshot["sense_ids"] == [second, first, second]
    assert learner.get(f"/api/v1/practice/sessions/{session['id']}").get_json()["data"]["items"] == session["items"]


@pytest.mark.parametrize(
    "extra",
    [{"sense_ids": []}, {"sense_ids": ["1"]}, {"sense_ids": 3}, {"sense_ids": [1], "focus": "weak"}],
)
def test_sense_ids_are_validated(learner, extra):
    response = start(learner, "recognition", 5, **extra)
    assert response.status_code == 422 and "sense_ids" in response.get_json()["error"]["fields"]


def test_senses_outside_target_are_not_issued(learner, db_config):
    outside = sorted(set(senses_of(db_config, "ielts-demo")) - set(senses_of(db_config, "cet6-demo")))[0]
    response = start(learner, "recognition", 5, sense_ids=[outside])
    assert response.status_code == 422 and response.get_json()["error"]["code"] == "NO_QUESTIONS"


def test_wrong_answer_drives_weak_practice_and_improvement_shows_in_diagnosis(learner, db_config):
    assert start(learner, "recognition", 5, focus="weak").get_json()["error"]["code"] == "NO_WEAK_ITEMS"
    weak_sense, solid_sense = senses_of(db_config, "cet6-demo")[:2]
    practice_once(learner, db_config, weak_sense, correct=False)
    practice_once(learner, db_config, solid_sense, correct=True)

    plan = learner.get("/api/v1/me/today").get_json()["data"]
    assert plan["weak"] == {"total": 1, "by_skill": {"recognition": 1, "spelling": 0, "context": 0}}
    [weak_entry] = current(learner)["weak"]
    assert (weak_entry["sense_id"], weak_entry["skill_type"], weak_entry["recent"]) == (
        weak_sense,
        "recognition",
        [False],
    )

    session = start(learner, "recognition", 10, focus="weak").get_json()["data"]
    [item] = session["items"]
    assert question_of(db_config, item["id"])["sense_id"] == weak_sense
    assert item["reason"]["code"] == "weak" and (item["reason"]["recent_wrong"], item["reason"]["recent_count"]) == (
        1,
        1,
    )
    assert answer(learner, item["id"], right(db_config, item["id"])).status_code == 200
    practice_once(learner, db_config, weak_sense, correct=True)
    practice_once(learner, db_config, weak_sense, correct=True)

    view = current(learner)
    assert view["weak"] == [] and [e["sense_id"] for e in view["improved"]] == [weak_sense]
    assert view["by_skill"]["recognition"]["improved"] == 1 and view["by_skill"]["recognition"]["tested"] == 2
    assert learner.get("/api/v1/me/today").get_json()["data"]["weak"]["total"] == 0
    page = learner.get("/insights").get_data(as_text=True)
    assert "当前状态" in page and "已改善" in page and "js/launch.js" in page


def test_skill_gap_lists_sense_strong_in_one_skill_weak_in_another(learner, db_config):
    sense = sorted(set(senses_of(db_config, "cet6-demo")) & set(senses_of(db_config, "cet6-demo", "spelling")))[0]
    practice_once(learner, db_config, sense, correct=True)
    [item] = targeted(learner, sense, "spelling")["items"]
    assert answer(learner, item["id"], "zzz").status_code == 200
    [gap] = current(learner)["skill_gaps"]
    assert (gap["sense_id"], gap["solid"], gap["weak"]) == (sense, ["recognition"], ["spelling"])


def test_review_list_has_strength_and_targeted_buttons(learner, db_config):
    sense = senses_of(db_config, "cet6-demo")[0]
    practice_once(learner, db_config, sense, correct=False)
    [entry] = learner.get("/api/v1/me/review").get_json()["data"]["wrong_pending"]
    assert entry["status"] == "weak" and entry["strength"] in (1, 2, 3, 4) and 0 < entry["recall"] <= 1
    page = learner.get("/review").get_data(as_text=True)
    assert f'data-senses="{sense}"' in page and "js/launch.js" in page


def test_early_correct_practice_keeps_interval_and_replays(demo, learner, db_config):
    sense = senses_of(db_config, "cet6-demo")[0]
    for _ in range(3):
        practice_once(learner, db_config, sense, correct=True)
    [state] = query(db_config, "SELECT * FROM learning_state")
    [first] = query(db_config, "SELECT submitted_at FROM attempts ORDER BY id LIMIT 1")
    assert (state["interval_stage"], state["correct_streak"], state["seen_count"]) == (1, 3, 3)
    assert (state["next_review_at"] - first["submitted_at"]).days == 1
    with demo.app_context():
        diffs, checked = learning_state.compare(db.get_db())
    assert (diffs, checked) == ([], 1)

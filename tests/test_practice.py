import json
import threading
from datetime import timedelta

import pytest

from app.clock import utc_now
from app.repositories import db
from app.repositories import practice as practice_repo
from app.services.content_import import import_content
from tests.helpers import (
    NOW,
    PASSWORD,
    answer,
    issue_until,
    login_as,
    query,
    question_of,
    right,
    select,
    start,
    wordbook_ids,
    wrong,
)

pytestmark = pytest.mark.db

# 目标词表


def test_wordbook_list_and_selection(demo, db_config):
    client = login_as(demo, "alice")
    listing = client.get("/api/v1/wordbooks").get_json()["data"]
    assert listing["total"] == 3 and {b["code"] for b in listing["items"]} == {
        "cet6-demo", "postgraduate-demo", "ielts-demo",
    }  # fmt: skip
    assert all(b["word_count"] == 30 and b["source"].startswith("项目自编演示") for b in listing["items"])
    only_ielts = client.get("/api/v1/wordbooks?exam_type=ielts").get_json()["data"]
    assert [b["code"] for b in only_ielts["items"]] == ["ielts-demo"]
    select(client, db_config, "cet6-demo", "ielts-demo")
    selected = {b["code"] for b in client.get("/api/v1/wordbooks").get_json()["data"]["items"] if b["selected"]}
    assert selected == {"cet6-demo", "ielts-demo"}


def test_invalid_wordbook_selection_changes_nothing(demo, db_config):
    client = login_as(demo, "alice")
    select(client, db_config, "cet6-demo")
    response = client.put("/api/v1/me/wordbooks", json={"wordbook_ids": [*wordbook_ids(db_config, "ielts-demo"), 999]})
    assert response.status_code == 422 and response.get_json()["error"]["fields"] == {"wordbook_ids": [999]}
    assert len(query(db_config, "SELECT * FROM user_wordbooks")) == 1


def test_wordbook_api_requires_login(demo):
    assert demo.test_client().get("/api/v1/wordbooks").status_code == 401


# 组卷


def test_session_requires_selected_target(demo, db_config):
    client = login_as(demo, "alice")
    response = start(client)
    assert response.status_code == 422 and response.get_json()["error"]["code"] == "NO_TARGET"
    select(client, db_config, "cet6-demo")
    not_mine = start(client, wordbook_ids=wordbook_ids(db_config, "ielts-demo"))
    assert not_mine.status_code == 422


@pytest.mark.parametrize("payload", [{"skill_type": "essay"}, {"count": 0}, {"count": 21}, {"count": "5"}])
def test_session_rejects_invalid_parameters(learner, payload):
    response = learner.post("/api/v1/practice/sessions", json={"skill_type": "recognition", "count": 10, **payload})
    assert response.status_code == 422


def test_session_has_distinct_senses_from_target_and_hides_answers(learner, db_config):
    response = start(learner, "spelling", 10)
    assert response.status_code == 201
    session = response.get_json()["data"]
    assert len(session["items"]) == 10 and session["total"] == 10 and session["answered"] == 0
    senses = query(
        db_config,
        "SELECT q.sense_id, q.skill_type FROM session_items i JOIN questions q ON q.id = i.question_id"
        " WHERE i.session_id = %s",
        (session["id"],),
    )
    assert len({r["sense_id"] for r in senses}) == 10 and {r["skill_type"] for r in senses} == {"spelling"}
    in_cet6 = query(
        db_config,
        "SELECT s.id FROM word_senses s JOIN wordbook_words m ON m.word_id = s.word_id"
        " JOIN wordbooks b ON b.id = m.wordbook_id WHERE b.code = 'cet6-demo'",
    )
    assert {r["sense_id"] for r in senses} <= {r["id"] for r in in_cet6}
    text = learner.get(f"/api/v1/practice/sessions/{session['id']}").get_data(as_text=True)
    assert "accepted" not in text and "option_id" not in text and "answers" not in text
    snapshot = json.loads(
        query(db_config, "SELECT target_snapshot_json FROM practice_sessions")[0]["target_snapshot_json"]
    )
    assert snapshot["skill_type"] == "spelling" and [b["code"] for b in snapshot["wordbooks"]] == ["cet6-demo"]


def test_inactive_and_retired_content_is_not_issued(learner, db_config):
    conn = db.connect(db_config)
    with conn.cursor() as cur:
        cur.execute("UPDATE words SET is_active = FALSE WHERE lemma_norm = 'abandon'")
        cur.execute("UPDATE questions SET status = 'retired' WHERE logical_key = 'access-1-recognition'")
    conn.commit()
    conn.close()
    cet6 = wordbook_ids(db_config, "cet6-demo")
    conn = db.connect(db_config)
    candidates = practice_repo.candidate_senses(conn, cet6, "recognition")
    conn.close()
    lemmas = {
        r["lemma_norm"]
        for r in query(db_config, "SELECT s.id, w.lemma_norm FROM word_senses s JOIN words w ON w.id = s.word_id")
        if r["id"] in candidates
    }
    # cet6 共 35 个词义：停用词条 abandon 与停用题目 access 的辨义题都不再可出。
    assert len(candidates) == 33 and "abandon" not in lemmas and "access" not in lemmas
    issued = {
        question_of(db_config, i["id"])["lemma_norm"]
        for i in start(learner, "recognition", 20).get_json()["data"]["items"]
    }
    assert issued <= lemmas


def test_priority_due_then_wrong_then_untested(demo, db_config):
    client = login_as(demo, "alice")
    select(client, db_config, "ielts-demo")
    user_id = query(db_config, "SELECT id FROM users WHERE username_norm = 'alice'")[0]["id"]
    senses = [
        r["id"]
        for r in query(
            db_config,
            "SELECT s.id FROM word_senses s JOIN wordbook_words m ON m.word_id = s.word_id"
            " JOIN wordbooks b ON b.id = m.wordbook_id WHERE b.code = 'ielts-demo' ORDER BY s.id",
        )
    ]
    due, wrong_sense, correct_sense = senses[:3]
    now = utc_now()
    states = [
        (due, 2, 2, 2, now - timedelta(hours=1)),
        (wrong_sense, 1, 0, 0, now + timedelta(minutes=5)),
        (correct_sense, 1, 1, 1, now + timedelta(days=1)),
    ]
    conn = db.connect(db_config)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO learning_state (user_id, sense_id, skill_type, seen_count, correct_count, correct_streak,"
            " next_review_at, last_attempt_at) VALUES (%s, %s, 'recognition', %s, %s, %s, %s, %s)",
            [
                (user_id, s, seen, correct, streak, nxt, now - timedelta(days=2))
                for s, seen, correct, streak, nxt in states
            ],
        )
    conn.commit()
    conn.close()
    items = start(client, "recognition", 3).get_json()["data"]["items"]
    chosen = [question_of(db_config, i["id"])["sense_id"] for i in items]
    assert chosen[:2] == [due, wrong_sense]
    assert chosen[2] not in (due, wrong_sense, correct_sense)


# 作答（T05—T08）


def test_grading_records_attempts_and_updates_learning_state(learner, db_config):
    items = start(learner, "recognition", 3).get_json()["data"]["items"]
    ok = answer(learner, items[0]["id"], right(db_config, items[0]["id"])).get_json()["data"]
    bad = answer(learner, items[1]["id"], wrong(db_config, items[1]["id"])).get_json()["data"]
    empty = answer(learner, items[2]["id"], "").get_json()["data"]
    assert (ok["is_correct"], ok["error_type"], ok["replayed"]) == (True, None, False)
    assert (bad["is_correct"], bad["error_type"]) == (False, "meaning")
    assert (empty["is_correct"], empty["error_type"]) == (False, "unanswered")
    assert ok["correct_answer"]["option_id"] == right(db_config, items[0]["id"])
    assert empty["session_status"] == "completed"
    attempts = query(db_config, "SELECT is_correct, error_type, review_rule_version FROM attempts ORDER BY id")
    assert [(a["is_correct"], a["error_type"]) for a in attempts] == [(1, None), (0, "meaning"), (0, "unanswered")]
    assert {a["review_rule_version"] for a in attempts} == {"review_rules_v1"}
    states = query(db_config, "SELECT seen_count, correct_count, interval_stage, next_review_at FROM learning_state")
    assert sorted((s["seen_count"], s["correct_count"], s["interval_stage"]) for s in states) == [
        (1, 0, 0), (1, 0, 0), (1, 1, 1),
    ]  # fmt: skip
    session = query(db_config, "SELECT status, finished_at FROM practice_sessions")[0]
    assert session["status"] == "completed" and session["finished_at"] is not None


def test_spelling_variant_and_case_are_accepted(demo, db_config):
    client = login_as(demo, "alice")
    select(client, db_config, "ielts-demo")
    by_lemma = issue_until(client, db_config, "spelling", ("analyse", "organise", "habitat"))
    assert answer(client, by_lemma["analyse"], "Analyze").get_json()["data"]["is_correct"] is True
    assert answer(client, by_lemma["organise"], "  ORGANISE ").get_json()["data"]["is_correct"] is True
    result = answer(client, by_lemma["habitat"], "habbitat").get_json()["data"]
    assert (result["is_correct"], result["error_type"], result["correct_answer"]["text"]) == (
        False,
        "spelling",
        "habitat",
    )


def test_malformed_answer_is_rejected_without_attempt(learner, db_config):
    item = start(learner, "recognition", 1).get_json()["data"]["items"][0]
    assert answer(learner, item["id"], "zz").status_code == 422
    assert learner.post(f"/api/v1/practice/items/{item['id']}/answer", json={}).status_code == 422
    assert query(db_config, "SELECT * FROM attempts") == []


def test_same_answer_replays_original_result(learner, db_config):
    item = start(learner, "recognition", 2).get_json()["data"]["items"][0]
    first = answer(learner, item["id"], right(db_config, item["id"])).get_json()["data"]
    again = answer(learner, item["id"], right(db_config, item["id"]))
    assert again.status_code == 200
    replay = again.get_json()["data"]
    assert replay["replayed"] is True and replay["submitted_at"] == first["submitted_at"]
    assert len(query(db_config, "SELECT * FROM attempts")) == 1
    assert query(db_config, "SELECT seen_count FROM learning_state")[0]["seen_count"] == 1


def test_concurrent_identical_submissions_count_once(demo, learner, db_config):
    other = demo.test_client()
    other.post("/auth/login", data={"username": "alice", "password": PASSWORD})
    item = start(learner, "recognition", 2).get_json()["data"]["items"][0]
    value = right(db_config, item["id"])
    barrier, results = threading.Barrier(2), []

    def submit(client):
        barrier.wait()
        results.append(answer(client, item["id"], value).get_json()["data"])

    threads = [threading.Thread(target=submit, args=(c,)) for c in (learner, other)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert len(query(db_config, "SELECT * FROM attempts")) == 1
    assert query(db_config, "SELECT seen_count FROM learning_state")[0]["seen_count"] == 1


def test_different_answer_after_submission_conflicts(learner, db_config):
    item = start(learner, "recognition", 2).get_json()["data"]["items"][0]
    answer(learner, item["id"], wrong(db_config, item["id"]))
    response = answer(learner, item["id"], right(db_config, item["id"]))
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "ALREADY_SUBMITTED"
    assert query(db_config, "SELECT is_correct FROM attempts")[0]["is_correct"] == 0


def test_failure_before_state_update_rolls_back_everything(learner, db_config, monkeypatch):
    item = start(learner, "recognition", 2).get_json()["data"]["items"][0]

    def broken(*args, **kwargs):
        raise RuntimeError("统计更新前中断")

    monkeypatch.setattr(practice_repo, "update_learning_state", broken)
    with pytest.raises(RuntimeError, match="统计更新前中断"):
        answer(learner, item["id"], right(db_config, item["id"]))
    assert query(db_config, "SELECT * FROM attempts") == []
    assert query(db_config, "SELECT * FROM learning_state") == []
    assert (
        query(db_config, "SELECT submitted_at FROM session_items WHERE id = %s", (item["id"],))[0]["submitted_at"]
        is None
    )


# 越权（T04）


def test_other_user_cannot_see_or_answer_session(demo, learner, db_config):
    session = start(learner, "recognition", 2).get_json()["data"]
    item = session["items"][0]
    mallory = login_as(demo, "mallory")
    peek = mallory.get(f"/api/v1/practice/sessions/{session['id']}")
    assert peek.status_code == 404 and item["prompt"] not in peek.get_data(as_text=True)
    attempt = answer(mallory, item["id"], right(db_config, item["id"]))
    assert attempt.status_code == 404 and query(db_config, "SELECT * FROM attempts") == []
    assert mallory.get("/api/v1/practice/sessions/999999").status_code == 404


# 题目版本（T10）与撤销目标


def test_old_session_keeps_original_question_version(learner, db_config, tmp_path):
    session = start(learner, "recognition", 1).get_json()["data"]
    item = session["items"][0]
    # 答错使该词义优先重出，便于确认新练习使用新版本。
    answer(learner, item["id"], wrong(db_config, item["id"]))
    v1 = question_of(db_config, item["id"])
    sense_key = query(db_config, "SELECT sense_key FROM word_senses WHERE id = %s", (v1["sense_id"],))[0]["sense_key"]
    row = {
        "logical_key": v1["logical_key"],
        "version": 2,
        "lemma_norm": v1["lemma_norm"],
        "sense_key": sense_key,
        "skill_type": "recognition",
        "prompt": v1["prompt"] + " 新版",
        "options": json.loads(v1["options_json"]),
        "answers": v1["answers"],
        "grading_policy": {"type": "choice"},
    }
    conn = db.connect(db_config)
    import_content(conn, {"questions.jsonl": json.dumps(row, ensure_ascii=False) + "\n"}, NOW)
    conn.close()
    old = learner.get(f"/api/v1/practice/sessions/{session['id']}").get_json()["data"]["items"][0]
    assert old["prompt"] == v1["prompt"] and old["result"]["is_correct"] is False
    reissued = issue_until(learner, db_config, "recognition", (v1["logical_key"],), key="logical_key")[
        v1["logical_key"]
    ]
    assert question_of(db_config, reissued)["version"] == 2


def test_deselecting_wordbook_keeps_history(learner, db_config):
    item = start(learner, "recognition", 1).get_json()["data"]["items"][0]
    answer(learner, item["id"], right(db_config, item["id"]))
    select(learner, db_config, "ielts-demo")
    assert len(query(db_config, "SELECT * FROM attempts")) == 1
    assert len(query(db_config, "SELECT * FROM learning_state")) == 1
    assert [
        r["code"]
        for r in query(db_config, "SELECT b.code FROM user_wordbooks u JOIN wordbooks b ON b.id = u.wordbook_id")
    ] == ["ielts-demo"]


# 页面


def test_pages_require_login_and_render(demo, learner):
    anonymous = demo.test_client()
    for path in ("/wordbooks", "/practice"):
        assert anonymous.get(path).status_code == 302
        page = learner.get(path)
        assert page.status_code == 200 and 'name="csrf-token"' in page.get_data(as_text=True)

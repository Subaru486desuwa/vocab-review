"""T17：学习诊断页与接口——规则统计、实验三遗忘风险、实验四错题语义，只读并留证。"""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from app.services import example_search, recall_model
from tests.helpers import NOW, answer, issue_until, login_as, query, question_of, right, select, start, wrong
from tests.test_ml_api import artifact, register  # noqa: F401  （复用小模型制品夹具）

pytestmark = pytest.mark.db

ENCODER = Path(__file__).resolve().parents[1] / "artifacts" / "dl" / "encoder"


@pytest.fixture(autouse=True)
def fresh_cache():
    recall_model.reset_cache()
    example_search.reset_cache()
    yield
    recall_model.reset_cache()
    example_search.reset_cache()


@pytest.fixture
def no_dl(demo, tmp_path):
    demo.config["DL_MODEL_DIR"] = str(tmp_path / "no-dl")
    return demo


def at(app, moment):
    app.config["CLOCK"] = lambda: moment


def insights(client):
    response = client.get("/api/v1/me/insights")
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def events(config):
    rows = query(config, "SELECT * FROM inference_events ORDER BY id")
    for row in rows:
        row["input"], row["output"] = json.loads(row["input_json"]), json.loads(row["output_json"])
    return rows


def snapshot(config):
    return (
        query(config, "SELECT * FROM attempts ORDER BY id"),
        query(config, "SELECT * FROM learning_state ORDER BY id"),
    )


def test_requires_login(demo):
    client = demo.test_client()
    assert client.get("/api/v1/me/insights").status_code == 401
    assert client.get("/insights").status_code == 302


def test_empty_history_has_no_model_calls(no_dl, learner, db_config):
    data = insights(learner)
    assert data["attempts"] == {"count": 0, "wrong": 0}
    assert (data["ml"]["status"], data["dl"]["status"]) == ("no_data", "no_data")
    assert events(db_config) == []
    assert "还没有作答记录" in learner.get("/insights").get_data(as_text=True)


def test_rules_follow_attempt_facts_and_stay_read_only(no_dl, learner, db_config):
    found = issue_until(learner, db_config, "recognition", {"fragile", "vulnerable"})
    chosen = wrong(db_config, found["fragile"])
    assert answer(learner, found["fragile"], chosen).status_code == 200
    assert answer(learner, found["vulnerable"], right(db_config, found["vulnerable"])).status_code == 200
    spelled = issue_until(learner, db_config, "spelling", {"benefit", "evidence"})
    answer(learner, spelled["benefit"], "benefi")
    answer(learner, spelled["evidence"], "eivdence")
    before = snapshot(db_config)

    data = insights(learner)
    assert data["attempts"] == {"count": 4, "wrong": 3}
    assert data["rules"]["error_types"] == {"meaning": 1, "spelling": 2}
    [confusion] = data["rules"]["confusions"]
    question = question_of(db_config, found["fragile"])
    options = {o["id"]: o["text"] for o in json.loads(question["options_json"])}
    assert (confusion["sense"]["lemma"], confusion["chosen"], confusion["count"]) == ("fragile", options[chosen], 1)
    assert confusion["correct"] == options[question["answers"]["option_id"]]
    assert confusion["chosen_sense"]["definition_zh"] == options[chosen]
    counts = data["rules"]["spelling"]["counts"]
    assert (counts["missing_letter"], counts["transposition"], sum(counts.values())) == (1, 1, 2)
    assert {e["lemma"] for e in data["rules"]["most_wrong"]} == {"benefit", "evidence", "fragile"}
    assert data["dl"]["status"] == "unavailable" and data["ml"]["status"] == "unavailable"
    assert snapshot(db_config) == before
    page = learner.get("/insights").get_data(as_text=True)
    assert "选错的选项" in page and "漏字母" in page and "模型不可用" in page


def test_ml_risk_matches_recall_api_and_is_logged(no_dl, db_config, artifact):  # noqa: F811
    no_dl.config["ML_MODEL_DIR"] = str(artifact)
    assert register(no_dl, artifact).exit_code == 0
    client = login_as(no_dl, "alice")
    select(client, db_config, "cet6-demo")
    at(no_dl, NOW)
    items = start(client, "recognition", 8).get_json()["data"]["items"]
    for i, item in enumerate(items):
        value = right(db_config, item["id"]) if i % 3 else wrong(db_config, item["id"])
        assert answer(client, item["id"], value).status_code == 200
    at(no_dl, NOW + timedelta(days=2))

    data = insights(client)
    ml = data["ml"]
    assert ml["status"] == "ok" and ml["items"] == 8 and len(ml["risk"]) == 8
    # 同一时刻作答，特征只有“答对/答错”两种取值，少于 3 种不分组
    assert ml["groups"] is None
    risk = ml["risk"][0]
    single = client.post(
        "/api/v1/ml/recall",
        json={"delta_seconds": 2 * 86400, "history_seen": risk["seen"], "history_correct": risk["correct"]},
    ).get_json()["data"]
    assert risk["expected_recall"] == round(single["expected_recall"], 4)
    values = [e["expected_recall"] for e in ml["risk"]]
    assert values == sorted(values)

    logged = [e for e in events(db_config) if e["source_type"] == "user_history"]
    assert [(e["kind"], e["status"]) for e in logged] == [("ml", "ok"), ("dl", "model_unavailable")]
    ml_event = logged[0]
    assert ml_event["model_version_id"] is not None and len(ml_event["input"]["items"]) == 8
    assert ml_event["output"]["groups"] is None and len(ml_event["output"]["expected_recall"]) == 8


@pytest.fixture
def dl_app(demo, tmp_path):
    if not (ENCODER / "encoder_manifest.json").is_file():
        pytest.skip("本地没有实验四编码器（python -m ml.download_encoder）")
    pytest.importorskip("sentence_transformers")
    (tmp_path / "dl").mkdir()
    (tmp_path / "dl" / "encoder").symlink_to(ENCODER)
    demo.config["DL_MODEL_DIR"] = str(tmp_path / "dl")
    result = demo.test_cli_runner().invoke(args=["build-example-index"])
    assert result.exit_code == 0, result.output
    return demo


def test_dl_groups_similar_wrong_senses_and_is_logged(dl_app, db_config):
    client = login_as(dl_app, "alice")
    select(client, db_config, "cet6-demo")
    found = issue_until(client, db_config, "recognition", {"fragile", "vulnerable", "notion"})
    for lemma in ("fragile", "vulnerable"):
        assert answer(client, found[lemma], wrong(db_config, found[lemma])).status_code == 200
    answer(client, found["notion"], right(db_config, found["notion"]))

    dl = insights(client)["dl"]
    assert dl["status"] == "ok" and dl["wrong_senses"] == 2
    [group] = dl["groups"]
    assert sorted(m["lemma"] for m in group["members"]) == ["fragile", "vulnerable"]
    assert dl["threshold"] < group["cohesion"] <= 1
    for c in dl["confusions"]:
        assert -1 <= c["similarity"] <= 1 and c["similar"] == (c["similarity"] >= dl["threshold"])
    [event] = [e for e in events(db_config) if e["kind"] == "dl" and e["source_type"] == "user_history"]
    assert event["status"] == "ok" and event["model_version_id"] is not None
    assert event["output"]["groups"] == [sorted(event["input"]["sense_ids"])]
    page = client.get("/insights").get_data(as_text=True)
    assert "错题语义" in page and "fragile" in page

import json
from pathlib import Path

import numpy as np
import pytest

from app.services import example_search
from tests.helpers import answer, login_as, query, right, select, start, wordbook_ids

pytestmark = pytest.mark.db

ENCODER = Path(__file__).resolve().parents[1] / "artifacts" / "dl" / "encoder"
if not (ENCODER / "encoder_manifest.json").is_file():
    pytest.skip("本地没有实验四编码器（python -m ml.download_encoder）", allow_module_level=True)
pytest.importorskip("sentence_transformers")

RIVER = "We sat on the grass beside the river."


@pytest.fixture(autouse=True)
def fresh_cache():
    example_search.reset_cache()
    yield
    example_search.reset_cache()


@pytest.fixture
def dl_app(demo, tmp_path):
    (tmp_path / "dl").mkdir()
    (tmp_path / "dl" / "encoder").symlink_to(ENCODER)
    demo.config["DL_MODEL_DIR"] = str(tmp_path / "dl")
    return demo


def build(app):
    result = app.test_cli_runner().invoke(args=["build-example-index"])
    assert result.exit_code == 0, result.output
    return result


def search(client, text=RIVER, **extra):
    return client.post("/api/v1/examples/search", json={"text": text, **extra})


def events(config):
    rows = query(config, "SELECT * FROM inference_events WHERE kind = 'dl' ORDER BY id")
    for row in rows:
        row["input"], row["output"] = json.loads(row["input_json"]), json.loads(row["output_json"])
    return rows


def test_missing_index_is_unavailable_and_logged(dl_app, db_config):
    client = login_as(dl_app, "alice")
    response = search(client)
    assert response.status_code == 503 and "flask build-example-index" in response.get_json()["error"]["message"]
    [event] = events(db_config)
    assert (event["status"], event["model_version_id"]) == ("model_unavailable", None)


def test_search_finds_the_right_sense_and_is_logged(dl_app, db_config):
    assert "158 条例句" in build(dl_app).output
    client = login_as(dl_app, "alice")
    data = search(client, top_k=3).get_json()["data"]
    assert len(data["results"]) == 3
    top = data["results"][0]
    assert (top["sense"]["lemma"], top["sense"]["sense_key"]) == ("bank", "2") and top["example_key"].startswith(
        "bank-2-"
    )
    scores = [r["cosine_similarity"] for r in data["results"]]
    assert scores == sorted(scores, reverse=True) and -1 <= scores[-1] <= scores[0] <= 1
    assert data["versions"]["revision"] == "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    assert data["versions"]["corpus_count"] == 158
    [event] = events(db_config)
    model_id = query(db_config, "SELECT id FROM model_versions WHERE kind = 'dl'")[0]["id"]
    assert event["model_version_id"] == model_id and event["source_type"] == "manual_lab"
    assert event["input"] == {"text": RIVER, "top_k": 3, "wordbook_id": None}
    assert [r["example_id"] for r in event["output"]["results"]] == [r["example_id"] for r in data["results"]]
    assert event["model_time_ms"] is not None and event["processing_time_ms"] >= event["model_time_ms"]


def test_money_bank_query_prefers_the_other_sense(dl_app):
    build(dl_app)
    client = login_as(dl_app, "alice")
    top = search(client, "I need to open a savings account at the bank.", top_k=1).get_json()["data"]["results"][0]
    assert (top["sense"]["lemma"], top["sense"]["sense_key"]) == ("bank", "1")


def test_wordbook_filter_limits_results(dl_app, db_config):
    build(dl_app)
    client = login_as(dl_app, "alice")
    ielts = wordbook_ids(db_config, "ielts-demo")[0]
    results = search(client, "a place to stay on holiday", top_k=10, wordbook_id=ielts).get_json()["data"]["results"]
    allowed = {
        r["lemma"]
        for r in query(
            db_config,
            "SELECT w.lemma FROM wordbook_words m JOIN words w ON w.id = m.word_id WHERE m.wordbook_id = %s",
            (ielts,),
        )
    }
    assert len(results) == 10 and {r["sense"]["lemma"] for r in results} <= allowed
    assert search(client, wordbook_id=999999).status_code == 422


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"text": "我们坐在河边的草地上"}, "text"),
        ({"text": "   "}, "text"),
        ({"text": RIVER, "top_k": 11}, "top_k"),
        ({"text": RIVER, "top_k": 0}, "top_k"),
        ({"text": "a " * 300}, "text"),
    ],
)
def test_invalid_queries_are_rejected_without_truncation(dl_app, db_config, payload, field):
    build(dl_app)
    client = login_as(dl_app, "alice")
    response = client.post("/api/v1/examples/search", json=payload)
    assert response.status_code == 422 and field in response.get_json()["error"]["fields"]
    assert events(db_config) == []


def test_over_token_limit_reports_count(dl_app):
    build(dl_app)
    client = login_as(dl_app, "alice")
    message = search(client, "a " * 300).get_json()["error"]["fields"]["text"]
    assert "超过上限 256" in message and "不截断" in message


def test_changed_corpus_rejects_old_index_until_rebuilt(dl_app, db_config):
    build(dl_app)
    client = login_as(dl_app, "alice")
    assert search(client).status_code == 200
    from app.repositories import db

    conn = db.connect(db_config)
    with conn.cursor() as cur:
        cur.execute("UPDATE examples SET is_active = FALSE WHERE example_key = 'bank-2-1'")
    conn.commit()
    conn.close()
    stale = search(client)
    assert stale.status_code == 503 and "过期" in stale.get_json()["error"]["message"]
    assert "157 条例句" in build(dl_app).output
    results = search(client, top_k=10).get_json()["data"]["results"]
    assert "bank-2-1" not in {r["example_key"] for r in results}


def test_tampered_index_is_refused(dl_app, tmp_path):
    build(dl_app)
    vectors = tmp_path / "dl" / "index" / "vectors.npy"
    np.save(vectors, np.zeros((158, 384), dtype=np.float32))
    client = login_as(dl_app, "alice")
    assert "哈希不符" in search(client).get_json()["error"]["message"]


def test_unregistered_encoder_is_refused(dl_app, db_config, tmp_path):
    from app.repositories import db, examples
    from ml import example_index

    conn = db.connect(db_config)
    with conn.cursor():
        rows = examples.active_examples(conn)
    conn.close()
    example_index.build(tmp_path / "dl", rows)
    client = login_as(dl_app, "alice")
    assert "未登记" in search(client).get_json()["error"]["message"]


def test_log_failure_is_not_reported_as_success(dl_app, monkeypatch):
    build(dl_app)
    client = login_as(dl_app, "alice")

    def broken(*args, **kwargs):
        raise RuntimeError("日志库不可用")

    monkeypatch.setattr("app.repositories.models.insert_inference_event", broken)
    response = search(client)
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "INFERENCE_LOG_FAILED"


def test_page_shows_state_and_practice_works_without_index(dl_app, db_config):
    client = login_as(dl_app, "alice")
    assert "检索不可用" in client.get("/examples").get_data(as_text=True)
    select(client, db_config, "cet6-demo")
    item = start(client, "recognition", 1).get_json()["data"]["items"][0]
    assert answer(client, item["id"], right(db_config, item["id"])).status_code == 200
    build(dl_app)
    example_search.reset_cache()
    assert "检索可用" in client.get("/examples").get_data(as_text=True)


def test_evaluation_command_labels_annotation_status(dl_app, tmp_path):
    build(dl_app)
    result = dl_app.test_cli_runner().invoke(args=["evaluate-example-search", "--out", str(tmp_path / "eval")])
    assert result.exit_code == 0, result.output
    metrics = json.loads((tmp_path / "eval" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["annotation_status"].startswith("AI 草拟")
    test = metrics["result"]["test"]
    assert test["sentence_embedding"]["with_relevant"] == 27 and test["tfidf"]["no_relevant"]["queries"] == 3
    assert "TF-IDF" in (tmp_path / "eval" / "evaluation.md").read_text(encoding="utf-8")

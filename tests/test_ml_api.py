import json
import shutil
import subprocess
import sys

import pytest

from app import create_app
from app.services import recall_model
from ml import prepare_recall_data, train_recall
from tests.helpers import login_as, query, right, select, start
from tests.test_ml_pipeline import _raw_file

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def artifact(tmp_path_factory):
    """用合成数据训练一个小模型，作为受信任的本地制品。"""
    root = tmp_path_factory.mktemp("ml")
    _raw_file(root / "raw.csv.gz")
    prepare_recall_data.prepare(root / "raw.csv.gz", root / "data", sample_rate=1.0, seed=42)
    train_recall.train(root / "data", root / "artifact", {**train_recall.CONFIG, "n_estimators": 5, "n_jobs": 1})
    return root / "artifact"


@pytest.fixture(autouse=True)
def fresh_cache():
    recall_model.reset_cache()
    yield
    recall_model.reset_cache()


@pytest.fixture
def ml_app(db_app, artifact):
    db_app.config["ML_MODEL_DIR"] = str(artifact)
    return db_app


def register(app, directory):
    return app.test_cli_runner().invoke(args=["register-model", str(directory)])


def recall(client, **payload):
    body = {"delta_seconds": 86400, "history_seen": 5, "history_correct": 4, **payload}
    return client.post("/api/v1/ml/recall", json=body)


def events(config):
    rows = query(config, "SELECT * FROM inference_events ORDER BY id")
    for row in rows:
        row["input"], row["output"] = json.loads(row["input_json"]), json.loads(row["output_json"])
    return rows


def test_unregistered_model_is_unavailable_and_logged(ml_app, db_config):
    client = login_as(ml_app, "alice")
    response = recall(client)
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "MODEL_UNAVAILABLE"
    [event] = events(db_config)
    assert (event["status"], event["model_version_id"], event["kind"]) == ("model_unavailable", None, "ml")
    assert "未登记" in event["output"]["reason"]


def test_registered_model_matches_offline_reference_and_is_logged(ml_app, artifact, db_config):
    assert register(ml_app, artifact).exit_code == 0
    assert "未修改" in register(ml_app, artifact).output
    client = login_as(ml_app, "alice")
    manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    for ref in manifest["reference_predictions"]:
        inputs = {k: ref[k] for k in ("delta_seconds", "history_seen", "history_correct")}
        data = recall(client, **inputs).get_json()["data"]
        if inputs["history_seen"] == 0:
            continue
        assert data["status"] == "ok" and data["expected_recall"] == ref["expected_recall"]
        assert data["model"] == {
            "model_code": "recall_rf",
            "version": "v1",
            "feature_schema_version": "recall_features_v1",
        }
    logged = events(db_config)
    assert len(logged) == len(manifest["reference_predictions"])
    model_id = query(db_config, "SELECT id FROM model_versions")[0]["id"]
    first = logged[0]
    assert first["model_version_id"] == model_id and first["source_type"] == "manual_lab"
    assert first["input"] == {"delta_seconds": 3600, "history_seen": 1, "history_correct": 1}
    assert first["model_time_ms"] is not None and first["processing_time_ms"] >= first["model_time_ms"]
    assert first["request_id"] and first["user_id"] is not None


def test_cold_start_and_invalid_input(ml_app, artifact, db_config):
    register(ml_app, artifact)
    client = login_as(ml_app, "alice")
    cold = recall(client, history_seen=0, history_correct=0).get_json()["data"]
    assert (cold["status"], cold["expected_recall"], cold["model_time_ms"]) == ("cold_start", None, None)
    bad = recall(client, history_seen=2, history_correct=3)
    assert bad.status_code == 422 and "history_correct" in bad.get_json()["error"]["fields"]
    assert recall(client, delta_seconds=-1).status_code == 422
    assert [e["status"] for e in events(db_config)] == ["cold_start"]


def test_tampered_or_mismatched_artifacts_are_refused(ml_app, artifact, db_config, tmp_path):
    register(ml_app, artifact)
    client = login_as(ml_app, "alice")
    tampered = tmp_path / "tampered"
    shutil.copytree(artifact, tampered)
    with open(tampered / "model.joblib", "ab") as f:
        f.write(b"x")
    ml_app.config["ML_MODEL_DIR"] = str(tampered)
    assert "哈希" in recall(client).get_json()["error"]["message"]
    other = tmp_path / "schema"
    shutil.copytree(artifact, other)
    manifest = json.loads((other / "manifest.json").read_text(encoding="utf-8"))
    (other / "manifest.json").write_text(json.dumps({**manifest, "feature_schema_version": "recall_features_v0"}))
    ml_app.config["ML_MODEL_DIR"] = str(other)
    assert "特征版本不符" in recall(client).get_json()["error"]["message"]
    assert register(ml_app, other).exit_code != 0


def test_same_version_with_different_artifact_cannot_be_registered(ml_app, artifact, tmp_path):
    register(ml_app, artifact)
    other = tmp_path / "retrained"
    shutil.copytree(artifact, other)
    with open(other / "model.joblib", "ab") as f:
        f.write(b"x")
    manifest = json.loads((other / "manifest.json").read_text(encoding="utf-8"))
    manifest["artifact"]["sha256"] = recall_model.sha256_file(other / "model.joblib")
    (other / "manifest.json").write_text(json.dumps(manifest))
    result = register(ml_app, other)
    assert result.exit_code != 0 and "新版本号" in result.output


def test_log_failure_is_not_reported_as_success(ml_app, artifact, monkeypatch):
    register(ml_app, artifact)
    client = login_as(ml_app, "alice")

    def broken(*args, **kwargs):
        raise RuntimeError("日志库不可用")

    monkeypatch.setattr("app.repositories.models.insert_inference_event", broken)
    response = recall(client)
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "INFERENCE_LOG_FAILED"


def test_requires_login_and_csrf(ml_app, artifact, db_config, migrated_db):
    register(ml_app, artifact)
    assert recall(ml_app.test_client()).status_code == 401
    strict = create_app({"TESTING": True, "SECRET_KEY": "t", "ML_MODEL_DIR": str(artifact), **db_config})
    client = strict.test_client()
    assert recall(client).status_code in (401, 403)


def test_lab_page_shows_model_state(ml_app, artifact):
    client = login_as(ml_app, "alice")
    assert "不可用" in client.get("/lab/ml").get_data(as_text=True)
    register(ml_app, artifact)
    recall_model.reset_cache()
    page = client.get("/lab/ml").get_data(as_text=True)
    assert "recall_rf" in page and "可用" in page and "MAE" in page


# T13：模型不可用时学习流程照常


def test_practice_works_while_model_is_missing(demo, db_config, tmp_path):
    demo.config["ML_MODEL_DIR"] = str(tmp_path / "missing")
    client = login_as(demo, "alice")
    select(client, db_config, "cet6-demo")
    item = start(client, "recognition", 1).get_json()["data"]["items"][0]
    assert (
        client.post(
            f"/api/v1/practice/items/{item['id']}/answer", json={"answer": right(db_config, item["id"])}
        ).status_code
        == 200
    )
    assert recall(client).status_code == 503
    assert "不可用" in client.get("/lab/ml").get_data(as_text=True)


def test_app_starts_without_model_dependencies():
    code = (
        "import sys; from app import create_app; create_app({'TESTING': True}).test_client().get('/');"
        "heavy = ('numpy', 'sklearn', 'joblib', 'pandas', 'torch', 'sentence_transformers');"
        "print(sorted(m for m in heavy if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"

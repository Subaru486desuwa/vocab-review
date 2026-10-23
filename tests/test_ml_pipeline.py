import gzip
import json
import math

import numpy as np
import pandas as pd
import pytest

from ml import prepare_recall_data as prep
from ml import train_recall
from ml.features import FEATURE_NAMES, build_recall_features, is_cold_start, validate_recall_input

HEADER = (
    "p_recall,timestamp,delta,user_id,learning_language,ui_language,lexeme_id,lexeme_string,"
    "history_seen,history_correct,session_seen,session_correct"
)


# M01：共享特征与输入检查


def test_features_follow_recall_features_v1():
    row = build_recall_features(86400, 4, 3)
    assert row.shape == (1, len(FEATURE_NAMES))
    assert row[0].tolist() == pytest.approx([math.log1p(1), math.log1p(4), math.log1p(3), 4 / 6])
    batch = build_recall_features(np.array([0, 43200]), np.array([1, 2]), np.array([0, 2]))
    assert batch.shape == (2, 4) and batch[1, 0] == pytest.approx(math.log1p(0.5))


@pytest.mark.parametrize(
    ("args", "field"),
    [
        ((-1, 1, 1), "delta_seconds"),
        ((float("nan"), 1, 1), "delta_seconds"),
        ((float("inf"), 1, 1), "delta_seconds"),
        (("10", 1, 1), "delta_seconds"),
        ((True, 1, 1), "delta_seconds"),
        ((10, 1.5, 1), "history_seen"),
        ((10, -1, 0), "history_seen"),
        ((10, 2, 3), "history_correct"),
        ((10, 2, False), "history_correct"),
    ],
)
def test_invalid_inputs_are_rejected(args, field):
    assert field in validate_recall_input(*args)


def test_valid_input_and_cold_start():
    assert validate_recall_input(0, 0, 0) == {} and is_cold_start(0)
    assert validate_recall_input(3600.5, 3, 3) == {} and not is_cold_start(3)


# 数据处理


def _raw_file(path):
    rows = []
    for user in range(40):
        for k in range(10):
            ts = 1_000_000 + k * 1000 + user
            rows.append(f"0.5,{ts},3600,u{user},en,es,id,word/word<n>,4,3,2,1")
    rows += [
        "0.5,1000500,3600,u0,es,en,id,palabra/palabra<n>,4,3,2,1",  # 非英语
        "0.5,1000501,-5,u1,en,es,id,bad/bad<n>,4,3,2,1",  # delta 为负
        "0.5,1000502,3600,u1,en,es,id,bad/bad<n>,0,0,2,1",  # 无历史
        "0.9,1000503,3600,u1,en,es,id,bad/bad<n>,4,3,2,1",  # p_recall 与 session 不符
        "0.5,1000504,3600,u1,en,es,id,bad/bad<n>,4,5,2,1",  # history_correct > history_seen
        "0.5,1000001,3600,u1,en,es,id,word/word<n>,4,3,2,1",  # 与已有行完全重复
    ]
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(HEADER + "\n" + "\n".join(rows) + "\n")


def test_prepare_filters_checks_samples_and_splits_by_time(tmp_path):
    raw = tmp_path / "raw.csv.gz"
    _raw_file(raw)
    manifest = prep.prepare(raw, tmp_path / "out", sample_rate=0.5, seed=42)
    assert manifest["rows"]["raw"] == 406 and manifest["rows"]["english"] == 405
    checks = manifest["checks_failed"]
    assert (checks["delta_negative"], checks["history_seen_not_positive"], checks["p_recall_mismatch"]) == (1, 1, 1)
    assert (checks["history_correct_out_of_range"], checks["exact_duplicate"]) == (1, 1)
    assert manifest["rows"]["after_checks"] == 400
    assert manifest["sampling"]["users_sampled"] == 20 and manifest["rows"]["sampled"] == 200
    parts = {n: pd.read_csv(tmp_path / "out" / f"{n}.csv.gz") for n in prep.SPLITS}
    assert sum(len(p) for p in parts.values()) == 200
    assert parts["train"]["timestamp"].max() < parts["validation"]["timestamp"].min()
    assert parts["validation"]["timestamp"].max() < parts["test"]["timestamp"].min()
    again = prep.prepare(raw, tmp_path / "again", sample_rate=0.5, seed=42)
    assert again["split"]["files"]["train"]["sha256"] == manifest["split"]["files"]["train"]["sha256"]


def test_equal_timestamps_stay_in_one_split():
    df = pd.DataFrame({"timestamp": [1] * 5 + [2] * 5, "user_id": list("abcdefghij"), "lexeme_string": ["x"] * 10})
    parts, cuts = prep.time_split(df)
    assert {len(parts["train"]), len(parts["validation"]), len(parts["test"])} == {10, 0}
    assert cuts["train_max_timestamp"] in (1, 2)


# 训练与制品（M02：导出后重新加载输出一致）


def test_train_writes_traceable_artifact(tmp_path):
    raw = tmp_path / "raw.csv.gz"
    _raw_file(raw)
    prep.prepare(raw, tmp_path / "data", sample_rate=1.0, seed=42)
    config = {**train_recall.CONFIG, "n_estimators": 5, "n_jobs": 1}
    manifest, metrics = train_recall.train(tmp_path / "data", tmp_path / "artifacts", config)
    files = {p.name for p in (tmp_path / "artifacts").iterdir()}
    assert files == {"model.joblib", "manifest.json", "metrics.json", "evaluation.md"}
    assert manifest["artifact"]["sha256"] == train_recall.sha256_file(tmp_path / "artifacts" / "model.joblib")
    assert manifest["feature_schema_version"] == "recall_features_v1"
    assert set(metrics["test"]["overall"]) == {"model", "baseline_train_label_mean", "baseline_smoothed_accuracy"}
    assert len(manifest["reference_predictions"]) == len(train_recall.REFERENCE_INPUTS)
    saved = json.loads((tmp_path / "artifacts" / "manifest.json").read_text(encoding="utf-8"))
    assert saved["data"]["source_sha256"] == prep.sha256_file(raw)
    assert "随机森林" in (tmp_path / "artifacts" / "evaluation.md").read_text(encoding="utf-8")

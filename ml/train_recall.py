"""训练、评价并导出实验三的随机森林回归制品。

python -m ml.train_recall [--data data/processed/recall_v1] [--out artifacts/ml]

使用 docs/models.md 记录的起点参数，未做超参搜索；validation 与 test 同时报告，
test 只在本脚本的最终运行中评价一次。输出 model.joblib、manifest.json、metrics.json、evaluation.md。
"""

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor

from ml.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, SECONDS_PER_DAY, build_recall_features

DATA = Path("data/processed/recall_v1")
OUT = Path("artifacts/ml")
MODEL_CODE = "recall_rf"
MODEL_VERSION = "v1"
CONFIG = {
    "estimator": "RandomForestRegressor",
    "n_estimators": 200,
    "max_depth": 12,
    "min_samples_leaf": 10,
    "random_state": 42,
    "n_jobs": -1,
    "tuning": "未做超参搜索：使用 docs/models.md 记录的起点参数",
}
# 固定输入，用于核对离线与 Web 输出一致（delta_seconds, history_seen, history_correct）。
REFERENCE_INPUTS = [(3600, 1, 1), (86400, 5, 4), (7 * 86400, 50, 45), (30 * 86400, 20, 10), (0, 3, 0)]
SPARSE_HISTORY = 3
LONG_INTERVAL_DAYS = 30


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def features_of(df):
    return build_recall_features(
        df["delta"].to_numpy(), df["history_seen"].to_numpy(), df["history_correct"].to_numpy()
    )


def _errors(y, prediction):
    error = prediction - y
    return {"mae": round(float(np.mean(np.abs(error))), 6), "rmse": round(float(np.sqrt(np.mean(error**2))), 6)}


def evaluate(df, model, train_label_mean):
    """逐记录 MAE/RMSE：模型、训练集标签均值、平滑历史正确率，以及子群与高误差样例。"""
    x, y = features_of(df), df["p_recall"].to_numpy()
    predictions = {
        "model": model.predict(x),
        "baseline_train_label_mean": np.full(len(y), train_label_mean),
        "baseline_smoothed_accuracy": x[:, FEATURE_NAMES.index("smoothed_accuracy")],
    }
    result = {
        "rows": len(df),
        "time_range_utc": [_iso(df["timestamp"].min()), _iso(df["timestamp"].max())],
        "overall": {name: _errors(y, p) for name, p in predictions.items()},
        "subgroups": {},
    }
    groups = {
        f"history_seen<={SPARSE_HISTORY}": df["history_seen"].to_numpy() <= SPARSE_HISTORY,
        f"delta>{LONG_INTERVAL_DAYS}d": df["delta"].to_numpy() > LONG_INTERVAL_DAYS * SECONDS_PER_DAY,
    }
    for label, mask in groups.items():
        result["subgroups"][label] = {
            "rows": int(mask.sum()),
            **({name: _errors(y[mask], p[mask]) for name, p in predictions.items()} if mask.any() else {}),
        }
    worst = np.argsort(-np.abs(predictions["model"] - y))[:10]
    result["largest_errors"] = [
        {
            "lexeme_string": df["lexeme_string"].iloc[i],
            "delta_days": round(float(df["delta"].iloc[i]) / SECONDS_PER_DAY, 2),
            "history_seen": int(df["history_seen"].iloc[i]),
            "history_correct": int(df["history_correct"].iloc[i]),
            "session_seen": int(df["session_seen"].iloc[i]),
            "p_recall": round(float(y[i]), 4),
            "prediction": round(float(predictions["model"][i]), 4),
        }
        for i in worst
    ]
    return result


def _iso(timestamp):
    return datetime.fromtimestamp(int(timestamp), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def reference_predictions(model):
    rows = np.array(REFERENCE_INPUTS, dtype=np.float64)
    predicted = model.predict(build_recall_features(rows[:, 0], rows[:, 1], rows[:, 2]))
    return [
        {"delta_seconds": d, "history_seen": s, "history_correct": c, "expected_recall": float(p)}
        for (d, s, c), p in zip(REFERENCE_INPUTS, predicted, strict=True)
    ]


def train(data=DATA, out=OUT, config=CONFIG):
    data, out = Path(data), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    splits = {name: pd.read_csv(data / f"{name}.csv.gz") for name in ("train", "validation", "test")}
    train_df = splits["train"]
    params = {k: v for k, v in config.items() if k not in ("estimator", "tuning")}
    model = RandomForestRegressor(**params)
    started = datetime.now(UTC)
    model.fit(features_of(train_df), train_df["p_recall"].to_numpy())
    fit_seconds = (datetime.now(UTC) - started).total_seconds()
    # 多线程预测时各树结果的累加顺序不固定，末位浮点会变；导出前改为单线程，离线与 Web 输出逐位一致。
    model.set_params(n_jobs=1)
    label_mean = float(train_df["p_recall"].mean())
    metrics = {
        "train_rows": len(train_df),
        "train_label_mean": round(label_mean, 6),
        "fit_seconds": round(fit_seconds, 1),
        "validation": evaluate(splits["validation"], model, label_mean),
        "test": evaluate(splits["test"], model, label_mean),
        "feature_importances": dict(
            zip(FEATURE_NAMES, (round(float(v), 4) for v in model.feature_importances_), strict=True)
        ),
    }
    model_path = out / "model.joblib"
    joblib.dump(model, model_path, compress=3)
    # 重新加载核对：导出的制品与内存中的模型输出一致。
    reloaded = joblib.load(model_path)
    references = reference_predictions(model)
    assert references == reference_predictions(reloaded), "导出后重新加载的预测不一致"
    data_manifest_path = data / "data_manifest.json"
    data_manifest = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    manifest = {
        "kind": "ml",
        "model_code": MODEL_CODE,
        "version": MODEL_VERSION,
        "task": "预测 Duolingo 源任务的 p_recall（一次练习内正确回忆比例），输出字段 expected_recall",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "artifact": {"file": model_path.name, "sha256": sha256_file(model_path), "bytes": model_path.stat().st_size},
        "train_config": config,
        "data": {
            "dataset": data_manifest["dataset"],
            "data_manifest_sha256": sha256_file(data_manifest_path),
            "source_sha256": data_manifest["source"]["sha256"],
            "source_license": data_manifest["source"]["license"],
            "sampling": data_manifest["sampling"],
            "split": {k: v for k, v in data_manifest["split"].items() if k != "files"},
            "split_files": {
                name: {k: f[k] for k in ("sha256", "rows")} for name, f in data_manifest["split"]["files"].items()
            },
        },
        "metrics_summary": {split: metrics[split]["overall"] for split in ("validation", "test")},
        "reference_predictions": references,
        "environment": {
            "python": sys.version.split()[0],
            "scikit-learn": sklearn.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
            "pandas": pd.__version__,
            "platform": platform.platform(),
        },
        "trained_at_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "evaluation.md").write_text(render_report(manifest, metrics, data_manifest), encoding="utf-8")
    return manifest, metrics


def render_report(manifest, metrics, data_manifest):
    """由 metrics 自动生成，数字不经手工转录。"""
    rows = data_manifest["rows"]
    sampling = data_manifest["sampling"]
    lines = [
        "# 实验三评价：预期练习正确比例回归",
        "",
        f"制品 {manifest['model_code']} {manifest['version']}，特征 {manifest['feature_schema_version']}，"
        f"训练于 {manifest['trained_at_utc']}（{metrics['fit_seconds']} 秒）。"
        "由 `python -m ml.train_recall` 自动生成。",
        "",
        "## 数据",
        "",
        f"- 来源：{data_manifest['source']['name']}（{data_manifest['source']['license']}），"
        f"文件 SHA-256 `{data_manifest['source']['sha256']}`。",
        f"- 行数：原始 {rows['raw']}，英语 {rows['english']}，"
        f"通过检查 {rows['after_checks']}，抽样后 {rows['sampled']}。",
        f"- 抽样：按用户，种子 {sampling['seed']}，比例 {sampling['rate']}，"
        f"{sampling['users_sampled']} / {sampling['users_total']} 名用户。",
        "- 检查未通过（一行可违反多条）："
        + "，".join(f"{k} {v}" for k, v in data_manifest["checks_failed"].items())
        + "。",
        "",
        "| 集合 | 行数 | 用户 | 时间范围（UTC） | 标签均值 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, f in data_manifest["split"]["files"].items():
        lines.append(
            f"| {name} | {f['rows']} | {f['users']} "
            f"| {f['time_range_utc'][0]} — {f['time_range_utc'][1]} | {f['label_mean']} |"
        )
    lines += ["", "## 逐记录误差", "", "| 集合 | 方法 | MAE | RMSE |", "| --- | --- | --- | --- |"]
    names = {
        "model": "随机森林",
        "baseline_train_label_mean": "训练集标签均值",
        "baseline_smoothed_accuracy": "平滑历史正确率",
    }
    for split in ("validation", "test"):
        for method, value in metrics[split]["overall"].items():
            lines.append(f"| {split} | {names[method]} | {value['mae']} | {value['rmse']} |")
    lines += ["", "## test 子群", "", "| 子群 | 行数 | 方法 | MAE | RMSE |", "| --- | --- | --- | --- | --- |"]
    for label, group in metrics["test"]["subgroups"].items():
        for method in names:
            if method in group:
                lines.append(
                    f"| {label} | {group['rows']} | {names[method]} "
                    f"| {group[method]['mae']} | {group[method]['rmse']} |"
                )
    lines += [
        "",
        "## test 误差最大的 10 条",
        "",
        "| lexeme | 间隔（天） | 历史 见/对 | 本次见 | p_recall | 预测 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in metrics["test"]["largest_errors"]:
        lines.append(
            f"| `{e['lexeme_string']}` | {e['delta_days']} "
            f"| {e['history_seen']}/{e['history_correct']} | {e['session_seen']} "
            f"| {e['p_recall']} | {e['prediction']} |"
        )
    lines += [
        "",
        "## 说明",
        "",
        "- 标签是一次练习内的正确回忆比例，不是掌握度、考试分数或严格校准的单次正确概率。",
        "- 时间切分只说明对后续时间段的表现；同一用户可同时出现在训练与测试中，不能据此推断对新用户的泛化。",
        "- 公开数据按 lexeme 计数，本系统按词义与题型计数，两者不直接等同；实验页输入为手工样例（manual_lab）。",
        "- 特征重要性：" + "，".join(f"{k} {v}" for k, v in metrics["feature_importances"].items()) + "。",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default=DATA)
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args(argv)
    manifest, metrics = train(args.data, args.out)
    print(json.dumps(manifest["metrics_summary"], ensure_ascii=False, indent=2))
    print("artifact", manifest["artifact"])


if __name__ == "__main__":
    main()

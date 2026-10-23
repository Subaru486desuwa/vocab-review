"""由 Duolingo halflife-regression 原始文件生成实验三的数据集。

python -m ml.prepare_recall_data [--raw 文件] [--out 目录] [--sample-rate 0.05] [--seed 42]

步骤：只保留 learning_language=en → 逐条规则检查并记录剔除数量 → 去除完全重复行 →
按用户固定种子抽样（保留完整时间序列）→ 按全局时间约 70/15/15 切分，同一时间戳不跨集合。
输出 train/validation/test.csv.gz 与 data_manifest.json。
"""

import argparse
import hashlib
import json
import math
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/settles.acl16.learning_traces.13m.csv.gz")
OUT = Path("data/processed/recall_v1")
SOURCE = {
    "name": "Duolingo halflife-regression learning traces",
    "url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/N8XJME",
    "referenced_by": "https://github.com/duolingo/halflife-regression",
    "license": "CC BY-NC 4.0",
    "citation": "Settles & Meeder (2016), A Trainable Spaced Repetition Model for Language Learning, ACL.",
}
KEEP = [
    "p_recall",
    "timestamp",
    "delta",
    "user_id",
    "lexeme_string",
    "history_seen",
    "history_correct",
    "session_seen",
    "session_correct",
]
SPLITS = ("train", "validation", "test")
P_RECALL_TOLERANCE = 1e-6


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_english(raw, chunksize=2_000_000):
    parts, raw_rows = [], 0
    for chunk in pd.read_csv(raw, chunksize=chunksize):
        raw_rows += len(chunk)
        parts.append(chunk.loc[chunk["learning_language"] == "en", KEEP])
    return pd.concat(parts, ignore_index=True), raw_rows


def check_rows(df):
    """返回 (通过检查的行, 各规则不通过的行数)。一行可同时违反多条规则，各自计数。"""
    numeric = ["p_recall", "timestamp", "delta", "history_seen", "history_correct", "session_seen", "session_correct"]
    rules = {
        "missing_value": df[KEEP].isna().any(axis=1),
        "history_seen_not_positive": df["history_seen"] <= 0,
        "delta_negative": df["delta"] < 0,
        "session_seen_not_positive": df["session_seen"] <= 0,
        "history_correct_out_of_range": (df["history_correct"] < 0) | (df["history_correct"] > df["history_seen"]),
        "session_correct_out_of_range": (df["session_correct"] < 0) | (df["session_correct"] > df["session_seen"]),
        "p_recall_out_of_range": (df["p_recall"] < 0) | (df["p_recall"] > 1),
    }
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = df["session_correct"] / df["session_seen"]
    rules["p_recall_mismatch"] = (df["p_recall"] - ratio).abs() > P_RECALL_TOLERANCE
    bad = np.zeros(len(df), dtype=bool)
    counts = {}
    for name, mask in rules.items():
        mask = mask.fillna(True).to_numpy()
        counts[name] = int(mask.sum())
        bad |= mask
    clean = df.loc[~bad].copy()
    for column in numeric:
        if column != "p_recall":
            clean[column] = clean[column].astype(np.int64)
    before = len(clean)
    clean = clean.drop_duplicates(keep="first")
    counts["exact_duplicate"] = before - len(clean)
    counts["removed_total"] = int(bad.sum()) + counts["exact_duplicate"]
    return clean.reset_index(drop=True), counts


def sample_users(df, rate, seed):
    users = np.sort(df["user_id"].unique())
    k = max(1, round(len(users) * rate))
    chosen = np.random.default_rng(seed).choice(users, size=k, replace=False)
    return df.loc[df["user_id"].isin(set(chosen))].reset_index(drop=True), len(users), k


def time_split(df, train_fraction=0.70, validation_fraction=0.15):
    """按时间戳切分；切点取对应分位处的时间戳，等于切点的行全部归入前一个集合。"""
    ts = np.sort(df["timestamp"].to_numpy())
    n = len(ts)
    cut_train = int(ts[math.ceil(n * train_fraction) - 1])
    cut_validation = int(ts[math.ceil(n * (train_fraction + validation_fraction)) - 1])
    parts = {
        "train": df.loc[df["timestamp"] <= cut_train],
        "validation": df.loc[(df["timestamp"] > cut_train) & (df["timestamp"] <= cut_validation)],
        "test": df.loc[df["timestamp"] > cut_validation],
    }
    ordered = {
        name: part.sort_values(["timestamp", "user_id", "lexeme_string"]).reset_index(drop=True)
        for name, part in parts.items()
    }
    return ordered, {"train_max_timestamp": cut_train, "validation_max_timestamp": cut_validation}


def _iso(timestamp):
    return datetime.fromtimestamp(int(timestamp), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def prepare(raw=RAW, out=OUT, sample_rate=0.05, seed=42):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    english, raw_rows = load_english(raw)
    clean, checks = check_rows(english)
    sampled, users_total, users_sampled = sample_users(clean, sample_rate, seed)
    splits, cuts = time_split(sampled)
    files = {}
    for name in SPLITS:
        path = out / f"{name}.csv.gz"
        splits[name].to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
        part = splits[name]
        files[name] = {
            "file": path.name,
            "sha256": sha256_file(path),
            "rows": len(part),
            "fraction": round(len(part) / len(sampled), 4),
            "users": int(part["user_id"].nunique()),
            "time_range_utc": [_iso(part["timestamp"].min()), _iso(part["timestamp"].max())] if len(part) else None,
            "label_mean": round(float(part["p_recall"].mean()), 6) if len(part) else None,
        }
    manifest = {
        "dataset": "recall_v1",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {**SOURCE, "file": Path(raw).name, "bytes": Path(raw).stat().st_size, "sha256": sha256_file(raw)},
        "filters": {"learning_language": "en", "p_recall_tolerance": P_RECALL_TOLERANCE},
        "rows": {"raw": raw_rows, "english": len(english), "after_checks": len(clean), "sampled": len(sampled)},
        "checks_failed": checks,
        "sampling": {
            "unit": "user_id",
            "rate": sample_rate,
            "seed": seed,
            "users_total": users_total,
            "users_sampled": users_sampled,
        },
        "split": {"method": "global_timestamp", "fractions": [0.7, 0.15, 0.15], **cuts, "files": files},
        "label": "p_recall：该次练习内正确回忆的比例（session_correct / session_seen）",
        "environment": {
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    (out / "data_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", default=RAW)
    parser.add_argument("--out", default=OUT)
    parser.add_argument("--sample-rate", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    manifest = prepare(args.raw, args.out, args.sample_rate, args.seed)
    print(json.dumps({k: manifest[k] for k in ("rows", "checks_failed", "sampling")}, ensure_ascii=False, indent=2))
    for name, info in manifest["split"]["files"].items():
        print(name, info["rows"], info["time_range_utc"])


if __name__ == "__main__":
    main()

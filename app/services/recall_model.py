"""实验三模型的加载与推理：只加载已登记、校验通过的本地制品，每个进程加载一次。

模型依赖（numpy、scikit-learn、joblib）在首次使用时才导入，未安装时模型不可用，其余功能照常运行。
"""

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.repositories import db
from app.repositories import models as repo

MANIFEST = "manifest.json"
_cache = {}
_lock = threading.Lock()


class ModelUnavailable(Exception):
    pass


@dataclass(frozen=True)
class LoadedModel:
    estimator: object
    manifest: dict
    model_version_id: int
    load_ms: float


def reset_cache():
    with _lock:
        _cache.clear()


def read_manifest(model_dir):
    path = Path(model_dir) / MANIFEST
    if not path.is_file():
        raise ModelUnavailable(f"缺少模型清单 {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelUnavailable("模型清单无法读取") from exc


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_artifact(model_dir, manifest):
    """校验清单与本进程环境、特征版本和制品哈希一致，返回制品路径。"""
    try:
        import sklearn

        from ml.features import FEATURE_SCHEMA_VERSION
    except ImportError as exc:
        raise ModelUnavailable("未安装模型依赖（构建镜像时 WITH_ML=1）") from exc
    if manifest.get("kind") != "ml":
        raise ModelUnavailable("清单不是实验三模型")
    if manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ModelUnavailable(
            f"特征版本不符：清单 {manifest.get('feature_schema_version')}，代码 {FEATURE_SCHEMA_VERSION}"
        )
    trained_with = manifest.get("environment", {}).get("scikit-learn")
    if trained_with != sklearn.__version__:
        raise ModelUnavailable(f"scikit-learn 版本不符：训练 {trained_with}，当前 {sklearn.__version__}")
    artifact = Path(model_dir) / manifest.get("artifact", {}).get("file", "")
    if not artifact.is_file():
        raise ModelUnavailable(f"缺少模型文件 {artifact}")
    if sha256_file(artifact) != manifest["artifact"].get("sha256"):
        raise ModelUnavailable("模型文件哈希与清单不符")
    return artifact


def get(conn, model_dir):
    """返回已加载的模型；失败不缓存，下次请求重新检查。"""
    key = str(Path(model_dir).resolve())
    with _lock:
        if key in _cache:
            return _cache[key]
        manifest = read_manifest(model_dir)
        artifact = verify_artifact(model_dir, manifest)
        with db.transaction(conn):
            row = repo.find_model_version(conn, manifest["model_code"], manifest["version"])
        if (
            row is None
            or row["status"] != "active"
            or row["kind"] != "ml"
            or row["artifact_sha256"] != manifest["artifact"]["sha256"]
            or row["feature_schema_version"] != manifest["feature_schema_version"]
        ):
            raise ModelUnavailable("模型未登记或登记信息与制品不符（flask register-model）")
        import joblib

        started = time.perf_counter()
        estimator = joblib.load(artifact)
        loaded = LoadedModel(estimator, manifest, row["id"], (time.perf_counter() - started) * 1000)
        _cache[key] = loaded
        return loaded


def predict(loaded, delta_seconds, history_seen, history_correct):
    """返回 (expected_recall, 特征, model_time_ms)；model_time_ms 只计特征构建与模型计算。"""
    from ml.features import build_recall_features

    started = time.perf_counter()
    features = build_recall_features(delta_seconds, history_seen, history_correct)
    value = float(loaded.estimator.predict(features)[0])
    elapsed = (time.perf_counter() - started) * 1000
    return min(max(value, 0.0), 1.0), [float(v) for v in features[0]], elapsed

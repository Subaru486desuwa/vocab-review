"""实验三：预期练习正确比例回归的实验页与推理接口；推理与留证都在学习写事务之外。"""

import json
import time
from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, request

from app import clock
from app.blueprints.auth import current_user, login_required
from app.blueprints.responses import api_error, api_ok, request_id
from app.repositories import db
from app.repositories import models as model_repo
from app.services import recall_model

bp = Blueprint("ml_lab", __name__)


def model_dir():
    path = Path(current_app.config["ML_MODEL_DIR"])
    return path if path.is_absolute() else Path(current_app.root_path).parent / path


def _log(status, payload, output, loaded=None, model_time_ms=None, processing_time_ms=None):
    with db.transaction() as conn:
        model_repo.insert_inference_event(
            conn,
            request_id=request_id(),
            user_id=current_user()["id"],
            model_version_id=loaded.model_version_id if loaded else None,
            kind="ml",
            source_type="manual_lab",
            input_json=json.dumps(payload, ensure_ascii=False),
            output_json=json.dumps(output, ensure_ascii=False),
            status=status,
            model_time_ms=model_time_ms,
            processing_time_ms=processing_time_ms,
            created_at=clock.now(),
        )


@bp.get("/lab/ml")
@login_required
def page():
    try:
        loaded = recall_model.get(db.get_db(), model_dir())
        status, reason = "available", None
    except recall_model.ModelUnavailable as exc:
        loaded, status, reason = None, "unavailable", str(exc)
    return render_template("lab/ml.html", status=status, reason=reason, manifest=loaded.manifest if loaded else None)


@bp.post("/api/v1/ml/recall")
@login_required
def recall():
    started = time.perf_counter()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "请求体必须是 JSON 对象")
    payload = {key: body.get(key) for key in ("delta_seconds", "history_seen", "history_correct")}
    try:
        loaded = recall_model.get(db.get_db(), model_dir())
    except recall_model.ModelUnavailable as exc:
        try:
            _log("model_unavailable", payload, {"reason": str(exc)})
        except Exception:
            current_app.logger.exception("推理失败事件写入失败")
        return api_error("MODEL_UNAVAILABLE", f"模型不可用：{exc}", 503)
    from ml.features import is_cold_start, validate_recall_input

    fields = validate_recall_input(*payload.values())
    if fields:
        return api_error("VALIDATION_FAILED", "参数校验失败", 422, fields=fields)
    manifest = loaded.manifest
    if is_cold_start(payload["history_seen"]):
        status, expected, features, model_time_ms = "cold_start", None, None, None
    else:
        expected, features, model_time_ms = recall_model.predict(loaded, *payload.values())
        status = "ok"
    output = {
        "status": status,
        "expected_recall": expected,
        "features": features,
        "model": {
            "model_code": manifest["model_code"],
            "version": manifest["version"],
            "feature_schema_version": manifest["feature_schema_version"],
        },
        "model_time_ms": None if model_time_ms is None else round(model_time_ms, 3),
    }
    output["processing_time_ms"] = round((time.perf_counter() - started) * 1000, 3)
    try:
        _log(status, payload, output, loaded, output["model_time_ms"], output["processing_time_ms"])
    except Exception:
        current_app.logger.exception("推理事件写入失败")
        return api_error("INFERENCE_LOG_FAILED", "推理结果未能留证，本次不作为实验样本", 503)
    return api_ok(output)

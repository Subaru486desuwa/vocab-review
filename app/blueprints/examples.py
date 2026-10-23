"""实验四：英语语境例句检索页面与接口；推理与留证都在学习写事务之外。"""

import json
import time
from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, request

from app import clock
from app.blueprints.auth import current_user, login_required
from app.blueprints.responses import api_error, api_ok, request_id
from app.repositories import db
from app.repositories import models as model_repo
from app.repositories import wordbooks as wordbook_repo
from app.services import example_search

bp = Blueprint("examples", __name__)


def dl_dir():
    path = Path(current_app.config["DL_MODEL_DIR"])
    return path if path.is_absolute() else Path(current_app.root_path).parent / path


def _log(status, payload, output, loaded=None, model_time_ms=None, processing_time_ms=None):
    with db.transaction() as conn:
        model_repo.insert_inference_event(
            conn,
            request_id=request_id(),
            user_id=current_user()["id"],
            model_version_id=loaded.model_version_id if loaded else None,
            kind="dl",
            source_type="manual_lab",
            input_json=json.dumps(payload, ensure_ascii=False),
            output_json=json.dumps(output, ensure_ascii=False),
            status=status,
            model_time_ms=model_time_ms,
            processing_time_ms=processing_time_ms,
            created_at=clock.now(),
        )


@bp.get("/examples")
@login_required
def page():
    try:
        loaded = example_search.get(db.get_db(), dl_dir())
        status, reason, info = "available", None, example_search.versions(loaded)
    except example_search.SearchUnavailable as exc:
        status, reason, info = "unavailable", str(exc), None
    with db.transaction() as conn:
        books = wordbook_repo.list_active(conn, current_user()["id"], None, 50, 0)
    return render_template("examples.html", status=status, reason=reason, info=info, wordbooks=books)


@bp.post("/api/v1/examples/search")
@login_required
def search():
    started = time.perf_counter()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "请求体必须是 JSON 对象")
    payload = {"text": body.get("text"), "top_k": body.get("top_k", 5), "wordbook_id": body.get("wordbook_id")}
    try:
        example_search.validate(*payload.values())
    except example_search.InvalidQuery as exc:
        return api_error("VALIDATION_FAILED", "参数校验失败", 422, fields=exc.fields)
    try:
        loaded = example_search.get(db.get_db(), dl_dir())
        results, model_time_ms = example_search.search(db.get_db(), loaded, *payload.values())
    except example_search.InvalidQuery as exc:
        return api_error("VALIDATION_FAILED", "参数校验失败", 422, fields=exc.fields)
    except example_search.SearchUnavailable as exc:
        try:
            _log("model_unavailable", payload, {"reason": str(exc)})
        except Exception:
            current_app.logger.exception("检索失败事件写入失败")
        return api_error("MODEL_UNAVAILABLE", f"例句检索不可用：{exc}", 503)
    output = {
        "status": "ok",
        "results": results,
        "versions": example_search.versions(loaded),
        "model_time_ms": round(model_time_ms, 3),
    }
    output["processing_time_ms"] = round((time.perf_counter() - started) * 1000, 3)
    logged = {
        **{k: output[k] for k in ("status", "versions", "model_time_ms", "processing_time_ms")},
        "results": [{"example_id": r["example_id"], "cosine_similarity": r["cosine_similarity"]} for r in results],
    }
    try:
        _log("ok", payload, logged, loaded, output["model_time_ms"], output["processing_time_ms"])
    except Exception:
        current_app.logger.exception("检索事件写入失败")
        return api_error("INFERENCE_LOG_FAILED", "检索结果未能留证，本次不作为实验样本", 503)
    return api_ok(output)

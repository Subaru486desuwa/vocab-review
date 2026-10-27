"""学习诊断页面与接口：规则统计不依赖模型；模型部分各自可失败，每次计算写一条 user_history 推理事件。"""

import json
import time

from flask import Blueprint, current_app, render_template

from app import clock
from app.blueprints.auth import current_user, login_required
from app.blueprints.examples import dl_dir
from app.blueprints.learning import SKILL_NAMES
from app.blueprints.ml_lab import model_dir
from app.blueprints.responses import api_ok, request_id
from app.repositories import db
from app.repositories import models as model_repo
from app.services import example_search, insights, recall_model

bp = Blueprint("insights", __name__)

SPELLING_NAMES = {
    "missing_letter": "漏字母",
    "extra_letter": "多字母",
    "wrong_letter": "错一个字母",
    "transposition": "相邻换位",
    "other": "差两处以上",
    "unanswered": "未作答",
}
ERROR_NAMES = {"meaning": "辨义", "context": "语境", "spelling": "拼写", "unanswered": "未作答", "unknown": "其他"}


def _log(kind, status, payload, output, model_version_id=None, model_time_ms=None, started=None):
    processing = None if started is None else round((time.perf_counter() - started) * 1000, 3)
    with db.transaction() as conn:
        model_repo.insert_inference_event(
            conn,
            request_id=request_id(),
            user_id=current_user()["id"],
            model_version_id=model_version_id,
            kind=kind,
            source_type="user_history",
            input_json=json.dumps(payload, ensure_ascii=False),
            output_json=json.dumps(output, ensure_ascii=False),
            status=status,
            model_time_ms=model_time_ms,
            processing_time_ms=processing,
            created_at=clock.now(),
        )


def _unavailable(kind, payload, exc):
    try:
        _log(kind, "model_unavailable", payload, {"reason": str(exc)})
    except Exception:
        current_app.logger.exception("诊断推理失败事件写入失败")
    return {"status": "unavailable", "reason": str(exc)}


def _ml(conn, items, sense_rows, started):
    if not items:
        return {"status": "no_data"}
    payload = {"items": items}
    try:
        loaded = recall_model.get(conn, model_dir())
    except recall_model.ModelUnavailable as exc:
        return _unavailable("ml", payload, exc)
    result, model_time_ms = insights.ml_analysis(loaded, items)
    manifest = loaded.manifest
    model = {k: manifest[k] for k in ("model_code", "version", "feature_schema_version")}
    model_time_ms = round(model_time_ms, 3)
    try:
        _log("ml", "ok", payload, {"model": model, **result}, loaded.model_version_id, model_time_ms, started)
    except Exception:
        current_app.logger.exception("诊断推理事件写入失败")
        return {"status": "log_failed"}
    view = insights.ml_view(items, result, sense_rows)
    return {"status": "ok", "model": model, "model_time_ms": model_time_ms, **view}


def _dl(conn, rule_result, rows, senses, sense_rows, started):
    wrong_ids, pairs, texts = insights.dl_inputs(rule_result, rows, senses)
    if not wrong_ids and not any(pairs):
        return {"status": "no_data"}
    from ml.diagnosis import SIMILAR_THRESHOLD

    payload = {"sense_ids": wrong_ids, "pairs": pairs, "threshold": SIMILAR_THRESHOLD}
    try:
        encoder = example_search.encoder(conn, dl_dir())
    except example_search.SearchUnavailable as exc:
        return _unavailable("dl", payload, exc)
    result, model_time_ms = insights.dl_analysis(encoder.model, wrong_ids, texts, pairs)
    model = {"model_code": example_search.MODEL_CODE, "revision": encoder.manifest["revision"]}
    model_time_ms = round(model_time_ms, 3)
    try:
        _log("dl", "ok", payload, {"model": model, **result}, encoder.model_version_id, model_time_ms, started)
    except Exception:
        current_app.logger.exception("诊断推理事件写入失败")
        return {"status": "log_failed"}
    view = sense_rows.get
    groups = [
        {"members": [insights.sense_summary(view(i)) for i in group], "cohesion": cohesion}
        for group, cohesion in zip(result["groups"], result["cohesion"], strict=True)
    ]
    confusions = [
        {**c, "similarity": sim, "similar": sim >= SIMILAR_THRESHOLD}
        for c, sim in zip(rule_result["confusions"], result["pair_similarity"], strict=True)
        if sim is not None
    ]
    return {
        "status": "ok",
        "model": model,
        "model_time_ms": model_time_ms,
        "threshold": SIMILAR_THRESHOLD,
        "wrong_senses": len(wrong_ids),
        "groups": groups,
        "confusions": confusions,
        "similar_count": sum(c["count"] for c in confusions if c["similar"]),
        "low_count": sum(c["count"] for c in confusions if not c["similar"]),
    }


def diagnose():
    started = time.perf_counter()
    conn = db.get_db()
    rows, senses, states = insights.load(conn, current_user()["id"])
    rule_result = insights.rules(rows, senses)
    sense_rows = {s["sense_id"]: s for s in senses}
    loaded = insights.load_current(conn, current_user()["id"], clock.now())
    return {
        "current": insights.current_view(*loaded) if loaded else None,
        "attempts": rule_result.pop("attempts"),
        "rules": rule_result,
        "ml": _ml(conn, insights.ml_inputs(states, clock.now()), sense_rows, started),
        "dl": _dl(conn, rule_result, rows, senses, sense_rows, started),
        "granularity": insights.GRANULARITY,
    }


@bp.get("/insights")
@login_required
def page():
    return render_template(
        "insights.html",
        data=diagnose(),
        skill_names=SKILL_NAMES,
        spelling_names=SPELLING_NAMES,
        error_names=ERROR_NAMES,
    )


@bp.get("/api/v1/me/insights")
@login_required
def insights_api():
    return api_ok(diagnose())

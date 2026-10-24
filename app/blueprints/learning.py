from flask import Blueprint, abort, render_template, request

from app import clock
from app.blueprints.auth import current_user, login_required
from app.blueprints.responses import api_error, api_ok
from app.repositories import db
from app.services import grading, practice, progress, today

bp = Blueprint("learning", __name__)

SKILL_NAMES = {"recognition": "辨义", "spelling": "拼写", "context": "语境"}


def _user_id():
    return current_user()["id"]


def _json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "请求体必须是 JSON 对象")
    return body


def _invalid(exc):
    return api_error("VALIDATION_FAILED", "参数校验失败", 422, fields=exc.fields)


# ---- 页面 ----


def _scope_args():
    wordbook_id = request.args.get("wordbook_id")
    if wordbook_id is not None:
        wordbook_id = int(wordbook_id) if wordbook_id.isdigit() else -1
    return {"wordbook_id": wordbook_id, "skill_type": request.args.get("skill_type") or None}


def _until(seconds):
    if seconds < 3600:
        return f"约 {max(1, round(seconds / 60))} 分钟后"
    if seconds < 86400:
        return f"约 {round(seconds / 3600)} 小时后"
    return f"约 {round(seconds / 86400)} 天后"


@bp.get("/dashboard")
@login_required
def dashboard():
    try:
        summary = progress.stats(db.get_db(), _user_id(), clock.now())
    except practice.NoTarget:
        summary = None
    return render_template("dashboard.html", user=current_user(), summary=summary, skill_names=SKILL_NAMES)


@bp.get("/today")
@login_required
def today_page():
    try:
        plan = today.plan(db.get_db(), _user_id(), clock.now())
    except practice.NoTarget:
        plan = None
    return render_template("today.html", plan=plan, skill_names=SKILL_NAMES)


@bp.get("/review")
@login_required
def review_page():
    try:
        data = progress.review_list(db.get_db(), _user_id(), clock.now())
    except practice.NoTarget:
        data = None
    if data:
        for entry in data["wrong_pending"]:
            entry["until"] = _until(entry["seconds_until_due"])
    return render_template("review.html", data=data, skill_names=SKILL_NAMES)


@bp.get("/wordbooks")
@login_required
def wordbooks_page():
    return render_template("wordbooks.html")


@bp.get("/practice")
@login_required
def practice_page():
    return render_template(
        "practice.html",
        skill_types=practice.SKILL_TYPES,
        default_count=practice.DEFAULT_COUNT,
        chosen_skill=request.args.get("skill_type"),
    )


# ---- JSON ----


@bp.get("/api/v1/wordbooks")
@login_required
def list_wordbooks():
    page = request.args.get("page", "1")
    try:
        data = practice.list_wordbooks(
            db.get_db(),
            _user_id(),
            exam_type=request.args.get("exam_type") or None,
            page=int(page) if page.isdigit() else -1,
        )
    except practice.InvalidRequest as exc:
        return _invalid(exc)
    return api_ok(data)


@bp.put("/api/v1/me/wordbooks")
@login_required
def set_wordbooks():
    try:
        targets = practice.set_targets(db.get_db(), _user_id(), _json_body().get("wordbook_ids"), clock.now())
    except practice.InvalidRequest as exc:
        return _invalid(exc)
    return api_ok({"wordbooks": targets})


@bp.post("/api/v1/practice/sessions")
@login_required
def create_session():
    body = _json_body()
    try:
        session = practice.create_session(
            db.get_db(),
            _user_id(),
            body.get("skill_type"),
            body.get("count", practice.DEFAULT_COUNT),
            body.get("wordbook_ids"),
            clock.now(),
            focus=body.get("focus"),
        )
    except practice.InvalidRequest as exc:
        return _invalid(exc)
    except practice.NoTarget:
        return api_error("NO_TARGET", "请先选择目标词表", 422)
    except practice.NoQuestions:
        return api_error("NO_QUESTIONS", "所选词表中没有该题型的可用题目", 422)
    return api_ok(session, 201)


@bp.get("/api/v1/me/today")
@login_required
def today_api():
    try:
        return api_ok(today.plan(db.get_db(), _user_id(), clock.now()))
    except practice.NoTarget:
        return api_error("NO_TARGET", "请先选择目标词表", 422)


@bp.get("/api/v1/me/review")
@login_required
def review_api():
    try:
        return api_ok(progress.review_list(db.get_db(), _user_id(), clock.now(), **_scope_args()))
    except practice.InvalidRequest as exc:
        return _invalid(exc)
    except practice.NoTarget:
        return api_error("NO_TARGET", "请先选择目标词表", 422)


@bp.get("/api/v1/me/stats")
@login_required
def stats_api():
    try:
        return api_ok(progress.stats(db.get_db(), _user_id(), clock.now(), **_scope_args()))
    except practice.InvalidRequest as exc:
        return _invalid(exc)
    except practice.NoTarget:
        return api_error("NO_TARGET", "请先选择目标词表", 422)


@bp.get("/api/v1/practice/sessions/<int:session_id>")
@login_required
def get_session(session_id):
    try:
        return api_ok(practice.get_session(db.get_db(), _user_id(), session_id))
    except practice.NotFound:
        return api_error("NOT_FOUND", "练习不存在", 404)


@bp.post("/api/v1/practice/items/<int:item_id>/answer")
@login_required
def submit_answer(item_id):
    body = _json_body()
    try:
        result = practice.submit_answer(db.get_db(), _user_id(), item_id, body.get("answer"), clock.now)
    except practice.NotFound:
        return api_error("NOT_FOUND", "题目不存在", 404)
    except grading.InvalidAnswer as exc:
        return api_error("INVALID_ANSWER", str(exc), 422)
    except practice.AlreadySubmitted:
        return api_error("ALREADY_SUBMITTED", "本题已提交其他答案；如需重练请开始新的练习", 409)
    except practice.SessionClosed:
        return api_error("SESSION_CLOSED", "练习已结束", 409)
    return api_ok(result)

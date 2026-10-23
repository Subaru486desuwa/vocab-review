from functools import wraps
from urllib.parse import urlsplit

from flask import Blueprint, abort, g, redirect, render_template, request, session, url_for

from app import clock
from app.blueprints.responses import api_error, api_ok, wants_json
from app.repositories import db, users
from app.services import accounts

bp = Blueprint("auth", __name__)

_INVALID_CREDENTIALS = "用户名或密码错误"
_USERNAME_TAKEN = "用户名已被使用"


def current_user():
    """会话中的有效用户；匿名访问不连接数据库。"""
    if "user" not in g:
        user = None
        user_id = session.get("user_id")
        if user_id is not None:
            with db.transaction() as conn:
                user = users.find_by_id(conn, user_id)
            if user is None or not user["is_active"]:
                session.clear()
                user = None
        g.user = user
    return g.user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            if wants_json():
                return api_error("UNAUTHENTICATED", "请先登录", 401)
            return redirect(url_for("auth.login_page", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user()["role"] != role:
                if wants_json():
                    return api_error("FORBIDDEN", "没有执行该操作的权限", 403)
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.app_context_processor
def inject_current_user():
    return {"current_user": current_user}


@bp.get("/login")
def login_page():
    return render_template("auth/login.html", next=request.args.get("next", ""))


@bp.get("/register")
def register_page():
    return render_template("auth/register.html")


@bp.post("/auth/register")
def register():
    username, password = _credentials()
    try:
        with db.transaction() as conn:
            user = accounts.register(conn, username, password, clock.now())
    except accounts.ValidationFailed as exc:
        if wants_json():
            return api_error("VALIDATION_FAILED", "字段校验失败", 422, fields=exc.fields)
        return render_template("auth/register.html", username=username, errors=exc.fields), 422
    except accounts.UsernameTaken:
        if wants_json():
            return api_error("USERNAME_TAKEN", _USERNAME_TAKEN, 409)
        return render_template("auth/register.html", username=username, errors={"username": _USERNAME_TAKEN}), 409
    _start_session(user)
    return api_ok(accounts.public_user(user), 201) if wants_json() else redirect(url_for("learning.dashboard"))


@bp.post("/auth/login")
def login():
    username, password = _credentials()
    with db.transaction() as conn:
        user = accounts.authenticate(conn, username, password)
    if user is None:
        if wants_json():
            return api_error("INVALID_CREDENTIALS", _INVALID_CREDENTIALS, 401)
        next_url = request.form.get("next", "")
        return render_template("auth/login.html", username=username, error=_INVALID_CREDENTIALS, next=next_url), 401
    _start_session(user)
    if wants_json():
        return api_ok(accounts.public_user(user))
    return redirect(_safe_next(request.form.get("next") or request.args.get("next")))


@bp.post("/auth/logout")
def logout():
    session.clear()
    return api_ok() if wants_json() else redirect(url_for("index"))


@bp.get("/api/v1/me")
@login_required
def me():
    return api_ok(accounts.public_user(current_user()))


def _credentials():
    payload = request.get_json(silent=True) if request.is_json else request.form
    if not isinstance(payload, dict):
        abort(400, "请求体必须是 JSON 对象")
    username, password = payload.get("username", ""), payload.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        abort(400, "username 与 password 必须是字符串")
    return username, password


def _start_session(user):
    # 登录前的会话内容一律丢弃，再写入身份。
    session.clear()
    session["user_id"] = user["id"]
    g.user = user


def _safe_next(target):
    default = url_for("learning.dashboard")
    if not target:
        return default
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return default
    return target

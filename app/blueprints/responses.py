import uuid

from flask import g, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_FAILED",
}


def wants_json():
    return request.path.startswith("/api/") or request.is_json


def request_id():
    """本次请求的标识；CSRF 等扩展可能先于本模块的钩子拒绝请求，因此按需生成。"""
    if "request_id" not in g:
        g.request_id = uuid.uuid4().hex
    return g.request_id


def api_ok(data=None, status=200):
    return jsonify(data=data, error=None, request_id=request_id()), status


def api_error(code, message, status, **details):
    return jsonify(data=None, error={"code": code, "message": message, **details}, request_id=request_id()), status


def init_app(app):
    @app.after_request
    def expose_request_id(response):
        response.headers["X-Request-ID"] = request_id()
        return response

    @app.errorhandler(CSRFError)
    def csrf_failed(exc):
        if wants_json():
            return api_error("CSRF_FAILED", "CSRF 校验失败，请刷新页面后重试", 403)
        return render_template("error.html", message="表单已过期或来源无效，请刷新页面后重试。"), 403

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if not wants_json():
            return exc
        return api_error(_CODES.get(exc.code, "HTTP_ERROR"), exc.description, exc.code)

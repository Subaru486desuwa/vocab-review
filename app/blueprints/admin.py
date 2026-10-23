from dataclasses import asdict

from flask import Blueprint, abort, request

from app import clock
from app.blueprints.auth import role_required
from app.blueprints.responses import api_error, api_ok
from app.repositories import db
from app.services import content_import

bp = Blueprint("admin", __name__)

_FIELDS = {name.split(".")[0]: name for name in content_import.SPECS}
_MAX_ROW_ERRORS = 200


@bp.post("/api/v1/admin/import")
@role_required("admin")
def import_content():
    """multipart 上传内容包；字段名为文件名去掉扩展名（words、questions 等），dry_run=1 只预检。"""
    unknown = sorted(set(request.files) - set(_FIELDS))
    if unknown:
        abort(400, "未知文件字段：" + "、".join(unknown))
    texts = {_FIELDS[field]: request.files[field].read() for field in request.files}
    if not texts:
        abort(400, "至少上传一个内容文件：" + "、".join(_FIELDS))
    dry_run = request.form.get("dry_run", "").lower() in ("1", "true")
    try:
        summary = content_import.import_content(db.get_db(), texts, clock.now(), dry_run=dry_run)
    except content_import.ImportFailed as exc:
        rows = [asdict(error) for error in exc.errors[:_MAX_ROW_ERRORS]]
        return api_error("IMPORT_INVALID", "预检未通过，未写入任何数据", 422, rows=rows, total_errors=len(exc.errors))
    return api_ok({"dry_run": dry_run, "summary": summary})

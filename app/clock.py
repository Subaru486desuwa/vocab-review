from datetime import UTC, datetime

from flask import current_app


def utc_now():
    """不带时区的 UTC 时间，与 MySQL DATETIME(6) 对应。"""
    return datetime.now(UTC).replace(tzinfo=None)


def now():
    """业务代码统一由此取时间；测试通过 app.config["CLOCK"] 固定时钟。"""
    return current_app.config["CLOCK"]()

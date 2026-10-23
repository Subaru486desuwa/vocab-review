from contextlib import contextmanager

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor


class DatabaseNotConfigured(RuntimeError):
    pass


def connect(config):
    """按配置新建连接；autocommit 关闭，会话时区固定为 UTC。"""
    missing = [key for key in ("DB_HOST", "DB_NAME", "DB_USER") if not config.get(key)]
    if missing:
        raise DatabaseNotConfigured("缺少数据库配置：" + ", ".join(missing))
    return pymysql.connect(
        host=config["DB_HOST"],
        port=int(config.get("DB_PORT") or 3306),
        user=config["DB_USER"],
        password=config.get("DB_PASSWORD") or "",
        database=config["DB_NAME"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        init_command="SET time_zone = '+00:00'",
    )


def get_db():
    """当前请求的连接，首次使用时创建。"""
    if "db" not in g:
        g.db = connect(current_app.config)
    return g.db


def close_db(exc=None):
    # 未提交的事务随连接关闭由服务端丢弃。
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@contextmanager
def transaction(conn=None):
    """显式事务：正常结束提交，任何异常回滚后继续抛出。"""
    conn = conn or get_db()
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    conn.commit()


def init_app(app):
    app.teardown_appcontext(close_db)

from datetime import datetime

import pytest

from app import create_app
from app.clock import now
from app.repositories import db

NOW = datetime(2026, 10, 24, 0, 0, 0)


class Boom(Exception):
    pass


def _insert_user(conn, name):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, username_norm, password_hash, created_at) VALUES (%s, %s, 'x', %s)",
            (name, name, NOW),
        )


def _count_users(config, name):
    conn = db.connect(config)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM users WHERE username_norm = %s", (name,))
            return cur.fetchone()["n"]
    finally:
        conn.close()


def test_connect_requires_explicit_target():
    with pytest.raises(db.DatabaseNotConfigured, match="DB_NAME"):
        db.connect({"DB_HOST": "db", "DB_USER": "u"})


def test_clock_can_be_fixed_through_config():
    app = create_app({"TESTING": True, "CLOCK": lambda: NOW})
    with app.app_context():
        assert now() == NOW


@pytest.mark.db
def test_transaction_commits_on_success(db_app, db_config):
    with db_app.app_context():
        with db.transaction() as conn:
            _insert_user(conn, "committed")
    assert _count_users(db_config, "committed") == 1


@pytest.mark.db
def test_transaction_rolls_back_on_error(db_app, db_config):
    with db_app.app_context():
        with pytest.raises(Boom), db.transaction() as conn:
            _insert_user(conn, "rolled_back")
            raise Boom
        # 若上面没有回滚，这次提交会把插入写入数据库。
        db.get_db().commit()
    assert _count_users(db_config, "rolled_back") == 0


@pytest.mark.db
def test_uncommitted_work_is_discarded_at_teardown(db_app, db_config):
    with db_app.app_context():
        _insert_user(db.get_db(), "dangling")
    assert _count_users(db_config, "dangling") == 0


@pytest.mark.db
def test_request_reuses_one_connection_and_closes_it(db_app):
    with db_app.app_context():
        conn = db.get_db()
        assert db.get_db() is conn
        with conn.cursor() as cur:
            cur.execute("SELECT @@session.time_zone AS tz, @@session.autocommit AS ac")
            row = cur.fetchone()
        assert (row["tz"], row["ac"]) == ("+00:00", 0)
    assert not conn.open

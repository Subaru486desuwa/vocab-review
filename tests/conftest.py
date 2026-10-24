import os

import pytest

from app import create_app
from app.clock import utc_now
from app.repositories import db, migrations
from app.services.content_import import import_content, read_directory
from tests.helpers import DEMO_PACKS, NOW, login_as, select


def _test_db_config():
    name = os.environ.get("TEST_DB_NAME")
    if not name:
        return None
    if not name.endswith("_test"):
        raise pytest.UsageError(f"TEST_DB_NAME={name} 不以 _test 结尾，拒绝清空")
    return {
        "DB_HOST": os.environ.get("DB_HOST"),
        "DB_PORT": os.environ.get("DB_PORT", "3306"),
        "DB_NAME": name,
        "DB_USER": os.environ.get("TEST_DB_USER"),
        "DB_PASSWORD": os.environ.get("TEST_DB_PASSWORD"),
    }


def _tables(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema = DATABASE()")
        return [row["name"] for row in cur.fetchall()]


def _reset(conn, keep=()):
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for name in _tables(conn):
            if name in keep:
                continue
            cur.execute(f"TRUNCATE TABLE `{name}`" if keep else f"DROP TABLE `{name}`")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()


@pytest.fixture(scope="session")
def db_config():
    # 未配置时跳过；已配置但连不上会直接报错，不当作通过。
    config = _test_db_config()
    if config is None:
        pytest.skip("未配置 TEST_DB_NAME，跳过需要 MySQL 的测试")
    return config


@pytest.fixture(scope="session")
def migrated_db(db_config):
    """清空测试库并从头执行全部迁移，返回本次执行的版本。"""
    conn = db.connect(db_config)
    try:
        _reset(conn)
        return migrations.upgrade(conn, utc_now())
    finally:
        conn.close()


@pytest.fixture
def db_conn(db_config, migrated_db):
    conn = db.connect(db_config)
    yield conn
    conn.rollback()
    _reset(conn, keep=("schema_migrations",))
    conn.close()


@pytest.fixture
def db_app(db_config, migrated_db):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": False, **db_config})
    yield app
    conn = db.connect(db_config)
    _reset(conn, keep=("schema_migrations",))
    conn.close()


@pytest.fixture
def table_names():
    return _tables


@pytest.fixture
def client(db_app):
    return db_app.test_client()


@pytest.fixture
def demo(db_app):
    with db_app.app_context():
        for pack in DEMO_PACKS:
            import_content(db.get_db(), read_directory(pack), NOW)
    return db_app


@pytest.fixture
def learner(demo, db_config):
    client = login_as(demo, "alice")
    select(client, db_config, "cet6-demo")
    return client

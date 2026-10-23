import re
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Blueprint

from app import create_app
from app.blueprints.auth import role_required
from app.repositories import db

pytestmark = pytest.mark.db

PASSWORD = "correct horse"


def register(client, username="alice", password=PASSWORD, **extra):
    return client.post("/auth/register", data={"username": username, "password": password, **extra})


def login(client, username="alice", password=PASSWORD):
    return client.post("/auth/login", data={"username": username, "password": password})


def user_row(config, username_norm):
    conn = db.connect(config)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username_norm = %s", (username_norm,))
            return cur.fetchone()
    finally:
        conn.close()


# T02：注册与密码哈希


def test_register_creates_learner_with_password_hash(client, db_config):
    response = register(client, username="Alice", role="admin")
    assert response.status_code == 302
    row = user_row(db_config, "alice")
    assert (row["username"], row["role"], row["display_timezone"]) == ("Alice", "learner", "Asia/Shanghai")
    assert row["password_hash"].startswith("scrypt:")
    assert PASSWORD not in row["password_hash"]


def test_register_rejects_case_insensitive_duplicate(client):
    register(client, username="alice")
    response = register(client, username="ALICE")
    assert response.status_code == 409
    assert "用户名已被使用" in response.get_data(as_text=True)


@pytest.mark.parametrize(
    ("username", "password"),
    [("ab", PASSWORD), ("a" * 33, PASSWORD), ("bad name", PASSWORD), ("a' OR '1'='1", PASSWORD), ("bob", "short")],
)
def test_register_rejects_invalid_fields(client, db_config, username, password):
    response = register(client, username=username, password=password)
    assert response.status_code == 422
    assert user_row(db_config, username.lower()) is None


def test_login_with_correct_password_sets_identity(client):
    register(client)
    client.post("/auth/logout")
    response = login(client, username="ALICE")
    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"
    assert client.get("/api/v1/me").get_json()["data"]["username"] == "alice"


@pytest.mark.parametrize(("username", "password"), [("alice", "wrong password"), ("nobody", PASSWORD)])
def test_wrong_password_and_unknown_user_get_the_same_answer(client, username, password):
    register(client)
    client.post("/auth/logout")
    response = login(client, username=username, password=password)
    assert response.status_code == 401
    assert "用户名或密码错误" in response.get_data(as_text=True)
    assert client.get("/api/v1/me").status_code == 401


def test_inactive_user_cannot_log_in(client, db_config):
    register(client)
    client.post("/auth/logout")
    conn = db.connect(db_config)
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET is_active = FALSE WHERE username_norm = 'alice'")
    conn.commit()
    conn.close()
    assert login(client).status_code == 401


def test_login_replaces_previous_session(client):
    register(client)
    with client.session_transaction() as sess:
        sess["stale"] = "x"
    login(client)
    with client.session_transaction() as sess:
        assert "stale" not in sess


@pytest.mark.parametrize("target", ["//evil.example/x", "https://evil.example/", "/dashboard"])
def test_login_redirect_stays_on_site(client, target):
    register(client)
    client.post("/auth/logout")
    response = client.post(f"/auth/login?next={target}", data={"username": "alice", "password": PASSWORD})
    assert response.headers["Location"] == "/dashboard"


# T03：退出与权限


def test_logout_requires_post(client):
    register(client)
    assert client.get("/auth/logout").status_code == 405
    assert client.get("/api/v1/me").status_code == 200
    assert client.post("/auth/logout").status_code == 302
    assert client.get("/api/v1/me").status_code == 401


def test_logged_out_api_gets_401_json_and_page_redirects(client):
    response = client.get("/api/v1/me")
    body = response.get_json()
    assert response.status_code == 401
    assert body["data"] is None and body["error"]["code"] == "UNAUTHENTICATED"
    assert re.fullmatch(r"[0-9a-f]{32}", body["request_id"])
    assert response.headers["X-Request-ID"] == body["request_id"]
    page = client.get("/dashboard")
    location = urlsplit(page.headers["Location"])
    assert page.status_code == 302
    assert (location.path, parse_qs(location.query)) == ("/login", {"next": ["/dashboard"]})


def test_learner_gets_403_on_admin_route(db_config, migrated_db):
    app = create_app({"TESTING": True, "SECRET_KEY": "t", "WTF_CSRF_ENABLED": False, **db_config})
    probe = Blueprint("probe", __name__)

    @probe.get("/api/v1/admin/probe")
    @role_required("admin")
    def admin_probe():
        return "ok"

    app.register_blueprint(probe)
    client = app.test_client()
    assert client.get("/api/v1/admin/probe").status_code == 401
    register(client)
    response = client.get("/api/v1/admin/probe")
    assert response.status_code == 403 and response.get_json()["error"]["code"] == "FORBIDDEN"


# JSON 与 CSRF


def test_json_login_uses_envelope(client):
    register(client)
    client.post("/auth/logout")
    ok = client.post("/auth/login", json={"username": "alice", "password": PASSWORD})
    assert ok.status_code == 200 and ok.get_json()["data"]["username"] == "alice"
    bad = client.post("/auth/login", json={"username": "alice", "password": "nope nope"})
    assert bad.status_code == 401 and bad.get_json()["error"]["code"] == "INVALID_CREDENTIALS"
    conflict = client.post("/auth/register", json={"username": "alice", "password": PASSWORD})
    assert conflict.status_code == 409 and conflict.get_json()["error"]["code"] == "USERNAME_TAKEN"


def test_post_without_csrf_token_is_rejected(db_config, migrated_db):
    app = create_app({"TESTING": True, "SECRET_KEY": "t", **db_config})
    client = app.test_client()
    assert register(client).status_code == 403
    assert client.post("/auth/login", json={"username": "a", "password": "b"}).get_json()["error"]["code"] == (
        "CSRF_FAILED"
    )
    assert user_row(db_config, "alice") is None


def test_page_form_carries_csrf_token(db_config, migrated_db):
    app = create_app({"TESTING": True, "SECRET_KEY": "t", **db_config})
    client = app.test_client()
    html = client.get("/register").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    response = client.post("/auth/register", data={"username": "alice", "password": PASSWORD, "csrf_token": token})
    assert response.status_code == 302


# 管理员命令


def test_create_admin_command(db_app, db_config):
    runner = db_app.test_cli_runner()
    result = runner.invoke(args=["create-admin", "--username", "Root_1"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert result.exit_code == 0, result.output
    assert user_row(db_config, "root_1")["role"] == "admin"
    again = runner.invoke(args=["create-admin", "--username", "root_1"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert again.exit_code != 0 and "用户名已被使用" in again.output

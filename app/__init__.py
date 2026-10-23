import os
import secrets

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from app import cli, clock
from app.blueprints import responses
from app.blueprints.admin import bp as admin_bp
from app.blueprints.auth import bp as auth_bp
from app.blueprints.lab import bp as lab_bp
from app.blueprints.learning import bp as learning_bp
from app.repositories import db

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        APP_ENV=os.environ.get("APP_ENV", "development"),
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("APP_ENV") == "production",
        DB_HOST=os.environ.get("DB_HOST"),
        DB_PORT=os.environ.get("DB_PORT", "3306"),
        DB_NAME=os.environ.get("DB_NAME"),
        DB_USER=os.environ.get("DB_USER"),
        DB_PASSWORD=os.environ.get("DB_PASSWORD"),
        CLOCK=clock.utc_now,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    if test_config is not None:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        # 登录依赖签名会话；只有测试配置允许使用临时密钥。
        if not app.config.get("TESTING"):
            raise RuntimeError("未设置 SECRET_KEY，拒绝启动；请在 .env 中填写随机值")
        app.config["SECRET_KEY"] = secrets.token_hex(16)
    csrf.init_app(app)
    db.init_app(app)
    cli.init_app(app)
    responses.init_app(app)
    app.register_blueprint(lab_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(learning_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app

import os

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from app import cli, clock
from app.blueprints.lab import bp as lab_bp
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
    )
    if test_config is not None:
        app.config.update(test_config)
    csrf.init_app(app)
    db.init_app(app)
    cli.init_app(app)
    app.register_blueprint(lab_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app

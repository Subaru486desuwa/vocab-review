import os

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from app.blueprints.lab import bp as lab_bp

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        APP_ENV=os.environ.get("APP_ENV", "development"),
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("APP_ENV") == "production",
    )
    if test_config is not None:
        app.config.update(test_config)
    csrf.init_app(app)
    app.register_blueprint(lab_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app

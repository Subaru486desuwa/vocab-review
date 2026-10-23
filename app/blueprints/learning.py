from flask import Blueprint, render_template

from app.blueprints.auth import current_user, login_required

bp = Blueprint("learning", __name__)


@bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user())

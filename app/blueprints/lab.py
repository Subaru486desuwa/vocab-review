from flask import Blueprint, render_template

bp = Blueprint("lab", __name__, url_prefix="/lab")


@bp.get("/hello")
def hello():
    return render_template("lab/hello.html")

from flask import Blueprint, render_template

pages_bp = Blueprint("pages_bp", __name__)

@pages_bp.route("/", defaults={"path": ""})
@pages_bp.route("/<path:path>")
def catch_all(path):
    return render_template("index.html")

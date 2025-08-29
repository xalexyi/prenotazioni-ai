from flask import Blueprint, render_template
from flask_login import login_required, current_user

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@bp.route("/")
@login_required
def index():
    # Passiamo il ristorante loggato per mostrare nome/logo in base.html
    return render_template("dashboard.html", restaurant=current_user)

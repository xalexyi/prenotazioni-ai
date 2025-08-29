from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@bp.route("/")
@login_required
def index():
    # Passiamo anche 'today' per i default dei campi data
    return render_template(
        "dashboard.html",
        restaurant=current_user,
        today=date.today().isoformat(),
    )

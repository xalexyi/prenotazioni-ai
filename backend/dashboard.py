from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import date

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@bp.route("/")
@login_required
def index():
    restaurant = current_user

    # È pizzeria se ha voci Pizza oppure se è la demo pizzeria
    is_pizzeria = False
    try:
        if getattr(restaurant, "pizzas", None) and len(restaurant.pizzas) > 0:
            is_pizzeria = True
    except Exception:
        is_pizzeria = False
    if getattr(restaurant, "slug", "") == "pizzerianapoli":
        is_pizzeria = True

    return render_template(
        "dashboard.html",
        restaurant=restaurant,
        is_pizzeria=is_pizzeria,
        today=date.today().isoformat(),
    )

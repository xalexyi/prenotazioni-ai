# backend/dashboard.py
from __future__ import annotations

from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@bp.route("/")
@login_required
def index():
    """
    Dashboard principale del ristorante loggato.
    - Rileva se il ristorante è una pizzeria (per mostrare KPI pizze).
    - Passa 'today' in formato YYYY-MM-DD per il filtro rapido.
    """
    restaurant = current_user  # Restaurant (flask-login)

    # È pizzeria se:
    #   1) slug demo specifico
    #   2) esistono voci Pizza collegate
    is_pizzeria = False
    try:
        if getattr(restaurant, "slug", "") == "pizzerianapoli":
            is_pizzeria = True
        elif hasattr(restaurant, "pizzas") and restaurant.pizzas:
            # .pizzas è una relationship; True se lista non vuota
            is_pizzeria = len(restaurant.pizzas) > 0
    except Exception:
        is_pizzeria = False

    return render_template(
        "dashboard.html",
        restaurant=restaurant,
        is_pizzeria=is_pizzeria,
        today=date.today().isoformat(),
    )

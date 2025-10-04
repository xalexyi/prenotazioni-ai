# -*- coding: utf-8 -*-
# backend/dashboard.py
from __future__ import annotations

from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@bp.route("/")
@login_required
def index():
    # Evito accessi a campi non garantiti: passo l'oggetto utente così com'è
    restaurant = current_user
    # flag pizzeria best-effort
    is_pizzeria = False
    try:
        if getattr(restaurant, "slug", "") == "pizzerianapoli":
            is_pizzeria = True
        elif hasattr(restaurant, "pizzas") and restaurant.pizzas:
            is_pizzeria = len(restaurant.pizzas) > 0
    except Exception:
        is_pizzeria = False

    return render_template(
        "dashboard.html",
        restaurant=restaurant,
        is_pizzeria=is_pizzeria,
        today=date.today().isoformat(),
    )

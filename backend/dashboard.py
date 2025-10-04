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
    r = current_user  # oggetto Restaurant

    # Flag e valori che il template si aspetta (con fallback così non rompe mai)
    ctx = {
        "restaurant": r,
        "today": date.today().isoformat(),

        # blocco “Chiamate attive 0/3” e simili
        "active_calls": 0,
        "max_calls": 3,

        # feature flags UI
        "is_pizzeria": bool(getattr(r, "slug", "") == "pizzerianapoli"),
        "has_hours": True,
        "has_special_days": True,
        "has_settings": True,

        # impostazioni default form (evitano buchi grafici)
        "default_timezone": "Europe/Rome",
        "default_step_min": 15,
        "default_last_order_min": 15,
        "default_min_people": 1,
        "default_max_people": 12,
        "default_capacity": 6,
    }

    return render_template("dashboard.html", **ctx)

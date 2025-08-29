from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from .models import db, Pizza, Restaurant

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@bp.route("/")
@login_required
def index():
    # Ristorante correntemente loggato (grazie a flask-login)
    r: Restaurant = current_user

    # Mostriamo le parti “pizzeria” solo se esiste un menu pizza per questo ristorante
    has_pizza_menu = db.session.query(Pizza.id)\
        .filter_by(restaurant_id=r.id).first() is not None

    return render_template(
        "dashboard.html",
        restaurant=r,
        today=date.today().isoformat(),
        pizza_mode=has_pizza_menu,
    )

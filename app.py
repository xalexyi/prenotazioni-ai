"""
Prenotazioni-AI — Backend Flask completo.
Gestisce login, dashboard API, orari, prenotazioni e impostazioni.
Compatibile con Render (Gunicorn) e PostgreSQL.
"""

from __future__ import annotations
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime
from flask_cors import CORS

# -----------------------------------------------------------------------------
# Configurazione globale
# -----------------------------------------------------------------------------

db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

    # Database
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///local.db"
    ).replace("postgres://", "postgresql://")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    # Login manager
    login_manager.init_app(app)
    login_manager.login_view = "login"

    # CORS
    CORS(app)

    # Import modelli
    from backend import models

    with app.app_context():
        db.create_all()

    # Registrazione routes
    register_routes(app)

    return app


# -----------------------------------------------------------------------------
# LOGIN HANDLER
# -----------------------------------------------------------------------------

from backend.models import User, Restaurant

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -----------------------------------------------------------------------------
# ROUTES FRONTEND (login / dashboard)
# -----------------------------------------------------------------------------

def register_routes(app: Flask):

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                resp = make_response(redirect(url_for("dashboard")))
                resp.set_cookie("theme", "dark", max_age=60 * 60 * 24 * 365)
                return resp
            return render_template("login.html", error="Credenziali non valide.")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        restaurant = Restaurant.query.get(current_user.restaurant_id)
        theme = request.cookies.get("theme", "dark")
        return render_template("dashboard.html", user=current_user, restaurant=restaurant, theme=theme)


    # -------------------------------------------------------------------------
    # API BACKEND (JSON)
    # -------------------------------------------------------------------------

    from backend.monolith import (
        list_reservations, create_reservation, update_reservation, delete_reservation,
        upsert_opening_hours, upsert_special_day,
        upsert_pricing, compute_stats, require_settings_for_restaurant
    )
    from backend.models import OpeningHours, SpecialDay, Settings, MenuItem

    # ---- Prenotazioni -------------------------------------------------------

    @app.route("/api/reservations", methods=["GET"])
    @login_required
    def api_get_reservations():
        q = request.args.get("q", "")
        day = request.args.get("day")
        data = list_reservations(current_user.restaurant_id, day, q)
        return jsonify(data)

    @app.route("/api/reservations", methods=["POST"])
    @login_required
    def api_create_reservation():
        payload = request.json
        rid = create_reservation(current_user.restaurant_id, payload)
        return jsonify({"success": True, "id": rid})

    @app.route("/api/reservations/<int:rid>", methods=["PUT"])
    @login_required
    def api_update_reservation(rid):
        payload = request.json
        update_reservation(current_user.restaurant_id, rid, payload)
        return jsonify({"success": True})

    @app.route("/api/reservations/<int:rid>", methods=["DELETE"])
    @login_required
    def api_delete_reservation(rid):
        delete_reservation(current_user.restaurant_id, rid)
        return jsonify({"success": True})

    # ---- Orari --------------------------------------------------------------

    @app.route("/api/hours", methods=["GET", "POST"])
    @login_required
    def api_hours():
        if request.method == "POST":
            upsert_opening_hours(current_user.restaurant_id, request.json)
            return jsonify({"success": True})
        rows = OpeningHours.query.filter_by(restaurant_id=current_user.restaurant_id).all()
        return jsonify({str(r.day_of_week): r.windows for r in rows})

    # ---- Giorni speciali ----------------------------------------------------

    @app.route("/api/special-days", methods=["GET", "POST"])
    @login_required
    def api_special_days():
        if request.method == "POST":
            d = request.json
            upsert_special_day(
                current_user.restaurant_id,
                d["date"],
                d.get("closed", False),
                d.get("windows", "")
            )
            return jsonify({"success": True})
        rows = SpecialDay.query.filter_by(restaurant_id=current_user.restaurant_id).all()
        return jsonify([
            {"date": r.date, "closed": r.closed, "windows": r.windows}
            for r in rows
        ])

    # ---- Prezzi / Impostazioni ---------------------------------------------

    @app.route("/api/settings", methods=["GET", "POST"])
    @login_required
    def api_settings():
        if request.method == "POST":
            upsert_pricing(current_user.restaurant_id, request.json)
            return jsonify({"success": True})
        s = require_settings_for_restaurant(current_user.restaurant_id)
        return jsonify({
            "avg_price": s.avg_price,
            "cover": s.cover,
            "seats_cap": s.seats_cap,
            "min_people": s.min_people,
            "menu_url": s.menu_url,
            "menu_desc": s.menu_desc,
        })

    # ---- Menu dinamico ------------------------------------------------------

    @app.route("/api/menu", methods=["GET", "POST", "DELETE"])
    @login_required
    def api_menu():
        if request.method == "POST":
            data = request.json
            item = MenuItem(
                restaurant_id=current_user.restaurant_id,
                name=data["name"],
                price=float(data["price"])
            )
            db.session.add(item)
            db.session.commit()
            return jsonify({"success": True, "id": item.id})
        elif request.method == "DELETE":
            iid = request.args.get("id")
            if iid:
                MenuItem.query.filter_by(
                    id=iid, restaurant_id=current_user.restaurant_id
                ).delete()
                db.session.commit()
            return jsonify({"success": True})
        rows = MenuItem.query.filter_by(restaurant_id=current_user.restaurant_id).all()
        return jsonify([{"id": r.id, "name": r.name, "price": r.price} for r in rows])

    # ---- Statistiche --------------------------------------------------------

    @app.route("/api/stats", methods=["GET"])
    @login_required
    def api_stats():
        day = request.args.get("day")
        stats = compute_stats(current_user.restaurant_id, day)
        return jsonify(stats)

    # ---- Tema (dark/light toggle) ------------------------------------------

    @app.route("/api/theme", methods=["POST"])
    def api_theme():
        theme = request.json.get("theme", "dark")
        resp = make_response(jsonify({"success": True, "theme": theme}))
        resp.set_cookie("theme", theme, max_age=60 * 60 * 24 * 365)
        return resp


# -----------------------------------------------------------------------------
# ENTRYPOINT PER GUNICORN
# -----------------------------------------------------------------------------

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

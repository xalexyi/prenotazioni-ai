import os
from datetime import datetime
from typing import Optional

from flask import (
    Flask, request, render_template, redirect, url_for,
    jsonify, flash, make_response
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user, UserMixin
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------------------------------------------------------------
# App-level singletons (db & login manager)
# ------------------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()


# ------------------------------------------------------------------------------
# App factory
# ------------------------------------------------------------------------------
def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app)

    # Config base (Render-ready)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    db_url = (os.getenv("DATABASE_URL") or "sqlite:///app.db").replace(
        "postgres://", "postgresql://"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Init estensioni
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login_page"

    # Import modelli DOPO init (evita circolari)
    # I modelli devono usare: from app import db
    with app.app_context():
        from backend.models import (  # noqa: F401
            User, Restaurant, Reservation, OpeningHours, SpecialDay, Settings
        )
        db.create_all()

    # --------------------------------------------------------------------------
    # User loader (Flask-Login)
    # --------------------------------------------------------------------------
    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[UserMixin]:
        try:
            from backend.models import User  # local import
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # Pagine: Login / Logout / Dashboard
    # --------------------------------------------------------------------------
    @app.route("/", methods=["GET", "POST"])
    def login_page():
        # Già autenticato → dashboard
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            from backend.models import User
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password_hash, password):
                flash("Credenziali non valide", "error")
                return render_template("login.html")

            remember = request.form.get("remember") == "on"
            login_user(user, remember=remember)
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        # NB: niente enumerate in Jinja — usare loop.index / loop.index0
        return render_template("dashboard.html")

    # --------------------------------------------------------------------------
    # Theme toggle (cookie)
    # --------------------------------------------------------------------------
    @app.post("/api/theme")
    def api_set_theme():
        """
        Body: {"theme":"dark" | "light"}
        Imposta un cookie 'theme' per ricordare la preferenza lato client.
        """
        data = request.get_json(silent=True) or {}
        theme = (data.get("theme") or "").lower().strip()
        if theme not in {"dark", "light"}:
            return jsonify({"ok": False, "error": "invalid_theme"}), 400
        resp = make_response(jsonify({"ok": True, "theme": theme}))
        # Cookie 30 giorni, Lax per Render
        resp.set_cookie("theme", theme, max_age=60 * 60 * 24 * 30, samesite="Lax")
        return resp

    # --------------------------------------------------------------------------
    # Helpers interni
    # --------------------------------------------------------------------------
    def require_settings_for_restaurant(rest_id: int):
        """Ritorna/imposta Settings per il ristorante (record unico)."""
        from backend.models import Settings
        s = Settings.query.filter_by(restaurant_id=rest_id).first()
        if not s:
            s = Settings(
                restaurant_id=rest_id,
                avg_price=25.0,
                cover=0.0,
                seats_cap=None,
                min_people=None,
                menu_url=None,
                menu_desc=None,
            )
            db.session.add(s)
            db.session.commit()
        return s

    # --------------------------------------------------------------------------
    # API: Prenotazioni
    # --------------------------------------------------------------------------
    @app.get("/api/reservations")
    @login_required
    def api_list_reservations():
        """
        Query param:
          - date=YYYY-MM-DD   (opzionale)
          - q=testo libero    (opzionale)
        """
        from backend.models import Reservation
        rest_id = current_user.restaurant_id
        q = (request.args.get("q") or "").strip().lower()
        day = request.args.get("date")

        query = Reservation.query.filter_by(restaurant_id=rest_id)
        if day:
            query = query.filter(Reservation.date == day)

        items = query.order_by(Reservation.date.asc(), Reservation.time.asc()).all()
        out = []
        for r in items:
            if q:
                blob = f"{r.name} {r.phone} {r.time} {r.status} {r.note or ''}".lower()
                if q not in blob:
                    continue
            out.append({
                "id": r.id,
                "date": r.date,   # stringa tipo "2025-10-12"
                "time": r.time,   # stringa tipo "20:30"
                "name": r.name,
                "phone": r.phone,
                "people": r.people,
                "status": r.status,
                "note": r.note,
            })
        return jsonify({"ok": True, "items": out})

    @app.post("/api/reservations")
    @login_required
    def api_create_reservation():
        """
        Body richiesto:
        {
          "date":"YYYY-MM-DD",
          "time":"HH:MM",
          "name":"Mario",
          "phone":"...",
          "people":2,
          "status":"Confermata" | "In attesa" | ... (facoltativo),
          "note":"..." (facoltativo)
        }
        """
        from backend.models import Reservation
        data = request.get_json(force=True) or {}
        try:
            r = Reservation(
                restaurant_id=current_user.restaurant_id,
                name=data["name"],
                phone=data.get("phone"),
                people=int(data.get("people") or 2),
                status=data.get("status") or "Confermata",
                note=data.get("note") or "",
                date=data["date"],
                time=data["time"],
            )
            db.session.add(r)
            db.session.commit()
            return jsonify({"ok": True, "id": r.id})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.put("/api/reservations/<int:rid>")
    @login_required
    def api_update_reservation(rid: int):
        """
        Body parziale consentito (solo campi presenti verranno aggiornati):
        name, phone, people, status, note, date, time
        """
        from backend.models import Reservation
        r = Reservation.query.filter_by(
            id=rid, restaurant_id=current_user.restaurant_id
        ).first_or_404()
        data = request.get_json(force=True) or {}

        for k in ["name", "phone", "status", "note"]:
            if k in data:
                setattr(r, k, data[k])
        if "people" in data and str(data["people"]).strip() != "":
            r.people = int(data["people"])
        if "date" in data and str(data["date"]).strip() != "":
            r.date = data["date"]
        if "time" in data and str(data["time"]).strip() != "":
            r.time = data["time"]

        try:
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.delete("/api/reservations/<int:rid>")
    @login_required
    def api_delete_reservation(rid: int):
        from backend.models import Reservation
        r = Reservation.query.filter_by(
            id=rid, restaurant_id=current_user.restaurant_id
        ).first_or_404()
        try:
            db.session.delete(r)
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # --------------------------------------------------------------------------
    # API: Orari settimanali
    # --------------------------------------------------------------------------
    @app.post("/api/hours")
    @login_required
    def api_save_hours():
        """
        Body:
        { "hours": { "0":"12:00-15:00, 19:00-22:30", "1":"...", ..., "6":"..." } }
        Tabella: opening_hours (day_of_week int, windows text)
        """
        from backend.models import OpeningHours
        rest_id = current_user.restaurant_id
        data = request.get_json(force=True) or {}
        hours = data.get("hours") or {}

        try:
            for d in range(7):
                win = hours.get(str(d), "")
                row = OpeningHours.query.filter_by(
                    restaurant_id=rest_id, day_of_week=d
                ).first()
                if not row:
                    row = OpeningHours(
                        restaurant_id=rest_id, day_of_week=d, windows=win
                    )
                    db.session.add(row)
                else:
                    row.windows = win
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # --------------------------------------------------------------------------
    # API: Giorni speciali
    # --------------------------------------------------------------------------
    @app.post("/api/special-days")
    @login_required
    def api_save_special_day():
        """
        Body:
        { "day":"YYYY-MM-DD", "closed":true/false, "windows":"12:00-15:00, 19:00-22:30" }
        Tabella: special_day (date text, closed bool, windows text)
        """
        from backend.models import SpecialDay
        rest_id = current_user.restaurant_id
        data = request.get_json(force=True) or {}
        try:
            day = data["day"]
            closed = bool(data.get("closed"))
            windows = data.get("windows") or ""

            row = SpecialDay.query.filter_by(restaurant_id=rest_id, date=day).first()
            if not row:
                row = SpecialDay(
                    restaurant_id=rest_id, date=day, closed=closed, windows=windows
                )
                db.session.add(row)
            else:
                row.closed = closed
                row.windows = windows

            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # --------------------------------------------------------------------------
    # API: Prezzi & Coperti  → settings
    # --------------------------------------------------------------------------
    @app.post("/api/pricing")
    @login_required
    def api_save_pricing():
        """
        Body (tutti facoltativi, vuoti ignorati):
        {
          "avg_price": 25.0,
          "cover": 0.0,
          "seats_cap": 60,
          "min_people": 2
        }
        """
        rest_id = current_user.restaurant_id
        data = request.get_json(force=True) or {}
        s = require_settings_for_restaurant(rest_id)

        try:
            if "avg_price" in data and str(data["avg_price"]).strip() != "":
                s.avg_price = float(data["avg_price"])
            if "cover" in data and str(data["cover"]).strip() != "":
                s.cover = float(data["cover"])
            if "seats_cap" in data and str(data["seats_cap"]).strip() != "":
                s.seats_cap = int(data["seats_cap"])
            if "min_people" in data and str(data["min_people"]).strip() != "":
                s.min_people = int(data["min_people"])
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # --------------------------------------------------------------------------
    # API: Menu digitale  → settings
    # --------------------------------------------------------------------------
    @app.post("/api/menu")
    @login_required
    def api_save_menu():
        """
        Body:
        { "menu_url":"https://...", "menu_desc":"testo opzionale" }
        """
        rest_id = current_user.restaurant_id
        data = request.get_json(force=True) or {}
        s = require_settings_for_restaurant(rest_id)
        try:
            s.menu_url = (data.get("menu_url") or "").strip() or None
            s.menu_desc = (data.get("menu_desc") or "").strip() or None
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # --------------------------------------------------------------------------
    # API: Stats (read-only)
    # --------------------------------------------------------------------------
    @app.get("/api/stats")
    @login_required
    def api_stats():
        from backend.models import Reservation
        rest_id = current_user.restaurant_id
        day = request.args.get("date")

        q = Reservation.query.filter_by(restaurant_id=rest_id)
        if day:
            q = q.filter(Reservation.date == day)
        total = q.count()

        avg_people = (
            db.session.query(db.func.avg(Reservation.people))
            .filter_by(restaurant_id=rest_id)
            .scalar()
        ) or 0.0

        s = require_settings_for_restaurant(rest_id)
        incasso_stimato = float(s.avg_price or 0.0) * float(total)

        return jsonify({
            "ok": True,
            "total_reservations": int(total),
            "avg_people": float(avg_people),
            "avg_price": float(s.avg_price or 0.0),
            "estimated_revenue": float(incasso_stimato),
        })

    # --------------------------------------------------------------------------
    # Healthcheck (per Render)
    # --------------------------------------------------------------------------
    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    # --------------------------------------------------------------------------
    # Error handlers puliti
    # --------------------------------------------------------------------------
    @app.errorhandler(404)
    def err_404(_e):
        # Se vuoi una pagina 404.html mettila in templates/
        return render_template("login.html"), 404

    @app.errorhandler(500)
    def err_500(_e):
        db.session.rollback()
        return render_template("login.html"), 500

    return app


# ------------------------------------------------------------------------------
# WSGI APP
# ------------------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    # Per esecuzione locale. Su Render viene ignorato e usa gunicorn.
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=True, host="0.0.0.0", port=port)

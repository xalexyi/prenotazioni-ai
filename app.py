import os
from datetime import datetime, date
from flask import Flask, request, render_template, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------------------------------------------------------
# Config & app
# -----------------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app)

    # Secret & DB
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///app.db"
    ).replace("postgres://", "postgresql://")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login_page"

    # Import models after db initialized
    from backend.models import User, Restaurant, Reservation, OpeningHours, SpecialDay, Settings  # noqa: F401

    # Create tables if not exist
    with app.app_context():
        db.create_all()

    @login_manager.user_loader
    def load_user(user_id: str):
        from backend.models import User  # local import
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # ------------------------------ Utilities ---------------------------------
    def normalize_day(value: str | None) -> str | None:
        """
        Converte '11/10/2025' -> '2025-10-11'.
        Accetta già '2025-10-11'. Restituisce None se vuoto/non valido.
        """
        if not value:
            return None
        s = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                d = datetime.strptime(s, fmt).date()
                return d.isoformat()  # YYYY-MM-DD
            except ValueError:
                continue
        # Non riconosciuto: ritorno None per evitare dati sporchi
        return None

    def require_settings_for_restaurant(rest_id: int):
        from backend.models import Settings
        s = Settings.query.filter_by(restaurant_id=rest_id).first()
        if not s:
            s = Settings(restaurant_id=rest_id, avg_price=25.0, cover=0.0,
                         seats_cap=None, min_people=None, menu_url=None, menu_desc=None)
            db.session.add(s)
            db.session.commit()
        return s

    # -----------------------------------------------------------------------------
    # Routes: Auth
    # -----------------------------------------------------------------------------
    @app.route("/", methods=["GET", "POST"])
    def login_page():
        # Se già autenticato → dashboard
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

            login_user(user, remember=(request.form.get("remember") == "on"))
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    # -----------------------------------------------------------------------------
    # Routes: Pages
    # -----------------------------------------------------------------------------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        # niente enumerate in jinja → si usa loop.index0
        return render_template("dashboard.html")

    # -----------------------------------------------------------------------------
    # API: Reservations
    # -----------------------------------------------------------------------------
    @app.get("/api/reservations")
    @login_required
    def api_list_reservations():
        from backend.models import Reservation
        rest_id = current_user.restaurant_id
        q = (request.args.get("q") or "").strip().lower()
        day_raw = request.args.get("date")
        day = normalize_day(day_raw)  # <— normalizza filtro

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
                "date": r.date,  # già YYYY-MM-DD
                "time": r.time,
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
        from backend.models import Reservation
        data = request.get_json(force=True) or {}
        try:
            day = normalize_day(data.get("date"))  # <— accetta dd/mm/yyyy
            if not day:
                return jsonify({"ok": False, "error": "Data non valida"}), 400

            r = Reservation(
                restaurant_id=current_user.restaurant_id,
                name=(data.get("name") or "").strip(),
                phone=(data.get("phone") or "").strip() or None,
                people=int(data.get("people") or 2),
                status=(data.get("status") or "Confermata").strip(),
                note=(data.get("note") or "").strip() or None,
                date=day,                       # <— salvato ISO
                time=(data.get("time") or "").strip(),  # es. '20:00'
            )
            db.session.add(r)
            db.session.commit()
            return jsonify({
                "ok": True,
                "item": {
                    "id": r.id,
                    "date": r.date,
                    "time": r.time,
                    "name": r.name,
                    "phone": r.phone,
                    "people": r.people,
                    "status": r.status,
                    "note": r.note,
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.put("/api/reservations/<int:rid>")
    @login_required
    def api_update_reservation(rid: int):
        from backend.models import Reservation
        r = Reservation.query.filter_by(id=rid, restaurant_id=current_user.restaurant_id).first_or_404()
        data = request.get_json(force=True) or {}
        for k in ["name", "phone", "status", "note"]:
            if k in data:
                val = (data[k] or "").strip()
                setattr(r, k, val or None if k in ("phone", "note") else val)
        if "people" in data:
            r.people = int(data["people"])
        if "date" in data:
            day = normalize_day(data["date"])
            if not day:
                return jsonify({"ok": False, "error": "Data non valida"}), 400
            r.date = day
        if "time" in data:
            r.time = (data["time"] or "").strip()
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
        r = Reservation.query.filter_by(id=rid, restaurant_id=current_user.restaurant_id).first_or_404()
        try:
            db.session.delete(r)
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # -----------------------------------------------------------------------------
    # API: Weekly hours & special days
    # -----------------------------------------------------------------------------
    @app.post("/api/hours")
    @login_required
    def api_save_hours():
        """Body: {hours:{ "0":"12:00-15:00, 19:00-22:30", ... }}  → opening_hours (day_of_week, windows)"""
        from backend.models import OpeningHours
        rest_id = current_user.restaurant_id
        data = request.get_json(force=True) or {}
        hours = data.get("hours") or {}

        try:
            for d in range(7):
                win = hours.get(str(d), "")
                row = OpeningHours.query.filter_by(restaurant_id=rest_id, day_of_week=d).first()
                if not row:
                    row = OpeningHours(restaurant_id=rest_id, day_of_week=d, windows=win)
                    db.session.add(row)
                else:
                    row.windows = win
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/api/special-days")
    @login_required
    def api_save_special_day():
        """Body: {day:'YYYY-MM-DD'| 'DD/MM/YYYY', closed:bool, windows:'..'}  → special_day"""
        from backend.models import SpecialDay
        rest_id = current_user.restaurant_id
        data = request.get_json(force=True) or {}
        try:
            day = normalize_day(data.get("day"))
            if not day:
                return jsonify({"ok": False, "error": "Data non valida"}), 400

            closed = bool(data.get("closed"))
            windows = (data.get("windows") or "").strip()

            row = SpecialDay.query.filter_by(restaurant_id=rest_id, date=day).first()
            if not row:
                row = SpecialDay(restaurant_id=rest_id, date=day, closed=closed, windows=windows)
                db.session.add(row)
            else:
                row.closed = closed
                row.windows = windows

            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # -----------------------------------------------------------------------------
    # API: Pricing (Prezzi & Coperti)  → table: settings
    # -----------------------------------------------------------------------------
    @app.post("/api/pricing")
    @login_required
    def api_save_pricing():
        from backend.models import Settings
        rest_id = current_user.restaurant_id
        data = request.get_json(force=True) or {}

        s = require_settings_for_restaurant(rest_id)
        try:
            if "avg_price" in data and data["avg_price"] != "":
                s.avg_price = float(data["avg_price"])
            if "cover" in data and data["cover"] != "":
                s.cover = float(data["cover"])
            if "seats_cap" in data and data["seats_cap"] != "":
                s.seats_cap = int(data["seats_cap"])
            if "min_people" in data and data["min_people"] != "":
                s.min_people = int(data["min_people"])
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # -----------------------------------------------------------------------------
    # API: Menu digitale → table: settings
    # -----------------------------------------------------------------------------
    @app.post("/api/menu")
    @login_required
    def api_save_menu():
        from backend.models import Settings
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

    # -----------------------------------------------------------------------------
    # API: Stats & report (read-only)
    # -----------------------------------------------------------------------------
    @app.get("/api/stats")
    @login_required
    def api_stats():
        from backend.models import Reservation, Settings
        rest_id = current_user.restaurant_id

        day = normalize_day(request.args.get("date"))
        q = Reservation.query.filter_by(restaurant_id=rest_id)
        if day:
            q = q.filter(Reservation.date == day)
        total = q.count()
        avg_people = (db.session.query(db.func.avg(Reservation.people))
                      .filter_by(restaurant_id=rest_id).scalar()) or 0

        s = require_settings_for_restaurant(rest_id)
        incasso_stimato = (s.avg_price or 0.0) * float(total)

        return jsonify({
            "ok": True,
            "total_reservations": total,
            "avg_people": float(avg_people),
            "avg_price": float(s.avg_price or 0.0),
            "estimated_revenue": float(incasso_stimato),
        })

    return app


# WSGI
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

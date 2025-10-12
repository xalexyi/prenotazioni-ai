import os
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user, login_required,
    current_user, UserMixin
)
from flask_cors import CORS
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------------------------------------------------------
# Configurazione principale
# -----------------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app)

    # Chiave segreta e database
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    default_sqlite = "sqlite:////opt/render/project/src/data/app.db"
    db_url = os.getenv("DATABASE_URL", default_sqlite)
    db_url = db_url.replace("postgres://", "postgresql://")

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login_page"

    # Import modelli
    from backend.models import (
        User, Restaurant, Reservation,
        OpeningHours, SpecialDay, Settings
    )

    # -------------------------------------------------------------------------
    # Creazione tabelle e colonne mancanti
    # -------------------------------------------------------------------------
    with app.app_context():
        db.create_all()
        _ensure_columns()

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # ROUTE: LOGIN / LOGOUT
    # -------------------------------------------------------------------------
    @app.route("/", methods=["GET", "POST"])
    def login_page():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
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

    # -------------------------------------------------------------------------
    # ROUTE: DASHBOARD
    # -------------------------------------------------------------------------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    # -------------------------------------------------------------------------
    # API HELPER: garantisce riga Settings per ogni ristorante
    # -------------------------------------------------------------------------
    def require_settings_for_restaurant(rest_id: int):
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
                menu_desc=None
            )
            db.session.add(s)
            db.session.commit()
        return s

    # -------------------------------------------------------------------------
    # API: Prenotazioni
    # -------------------------------------------------------------------------
    @app.get("/api/reservations")
    @login_required
    def api_list_reservations():
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
                "date": r.date,
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
            r = Reservation(
                restaurant_id=current_user.restaurant_id,
                name=data["name"],
                phone=data.get("phone"),
                people=int(data.get("people") or 2),
                status=data.get("status") or "Confermata",
                note=data.get("note") or "",
                date=data["date"],  # "YYYY-MM-DD"
                time=data["time"],  # "HH:MM"
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
        from backend.models import Reservation
        r = Reservation.query.filter_by(
            id=rid, restaurant_id=current_user.restaurant_id
        ).first_or_404()
        data = request.get_json(force=True) or {}
        for k in ["name", "phone", "status", "note"]:
            if k in data:
                setattr(r, k, data[k])
        if "people" in data:
            r.people = int(data["people"])
        if "date" in data:
            r.date = data["date"]
        if "time" in data:
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

    # -------------------------------------------------------------------------
    # API: Orari settimanali e giorni speciali
    # -------------------------------------------------------------------------
    @app.post("/api/hours")
    @login_required
    def api_save_hours():
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

    @app.post("/api/special-days")
    @login_required
    def api_save_special_day():
        from backend.models import SpecialDay
        rest_id = current_user.restaurant_id
        data = request.get_json(force=True) or {}
        try:
            day = data["day"]
            closed = bool(data.get("closed"))
            windows = data.get("windows") or ""
            row = SpecialDay.query.filter_by(
                restaurant_id=rest_id, date=day
            ).first()
            if not row:
                row = SpecialDay(
                    restaurant_id=rest_id, date=day,
                    closed=closed, windows=windows
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

    # -------------------------------------------------------------------------
    # API: Prezzi & coperti (settings)
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # API: Menu digitale
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # API: Statistiche
    # -------------------------------------------------------------------------
    @app.get("/api/stats")
    @login_required
    def api_stats():
        from backend.models import Reservation, Settings
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
            or 0
        )
        s = require_settings_for_restaurant(rest_id)
        incasso_stimato = (s.avg_price or 0.0) * float(total)
        return jsonify({
            "ok": True,
            "total_reservations": total,
            "avg_people": float(avg_people),
            "avg_price": float(s.avg_price or 0.0),
            "estimated_revenue": float(incasso_stimato),
        })

    # -------------------------------------------------------------------------
    # Health check per Render
    # -------------------------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return "OK", 200

    return app


# -----------------------------------------------------------------------------
# Funzione di migrazione sicura (evita crash)
# -----------------------------------------------------------------------------
def _ensure_columns():
    stmts = [
        # esempio di colonne aggiuntive se mancanti
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password_hash TEXT',
    ]
    for s in stmts:
        try:
            db.session.execute(text(s))
            db.session.commit()
        except Exception as e:
            print("DB MIGRATION SKIPPED:", e)
            db.session.rollback()


# -----------------------------------------------------------------------------
# Esegui server locale
# -----------------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))

import os
from datetime import date, datetime
from typing import Optional

from flask import (
    Flask, render_template, request, redirect, url_for, jsonify, flash
)
from flask_login import (
    LoginManager, login_user, login_required, logout_user, current_user
)
from werkzeug.security import check_password_hash

# I NOSTRI MODELLI vivono in backend/models.py e contengono l'istanza db
from backend.models import (
    db, User, Restaurant, Reservation, WeeklyHours, SpecialDay,
    MenuItem, Settings
)


def _boolean(val: str) -> bool:
    return str(val).lower() in {"1", "true", "t", "yes", "y", "on"}


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # ---- Config
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-it")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///instance/app.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ---- DB & Login
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.login_view = "login_page"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[User]:
        return User.query.get(int(user_id))

    # ---- Creazione tabelle all’avvio
    with app.app_context():
        db.create_all()

    # ------------------ ROUTES PAGINE ------------------

    @app.route("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login_page"))

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            remember = bool(request.form.get("remember"))
            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password_hash, password):
                flash("Credenziali non valide.", "warn")
                return render_template("login.html")
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
        return render_template("dashboard.html", selected_date=date.today().strftime("%d/%m/%Y"))

    # ------------------ API PRENOTAZIONI ------------------

    @app.get("/api/reservations")
    @login_required
    def api_list_reservations():
        """?date=YYYY-MM-DD&q=term"""
        d = request.args.get("date")
        q = (request.args.get("q") or "").strip()

        query = Reservation.query.filter_by(restaurant_id=current_user.restaurant_id)

        if d:
            try:
                when = datetime.strptime(d, "%Y-%m-%d").date()
                query = query.filter(Reservation.date == when)
            except Exception:
                pass

        if q:
            like = f"%{q}%"
            query = query.filter(
                (Reservation.name.ilike(like)) |
                (Reservation.phone.ilike(like)) |
                (Reservation.time.ilike(like))
            )

        items = []
        for r in query.order_by(Reservation.date.asc(), Reservation.time.asc()).all():
            items.append({
                "id": r.id,
                "date": r.date.strftime("%Y-%m-%d"),
                "time": r.time,
                "name": r.name,
                "phone": r.phone or "",
                "people": r.people,
                "status": r.status or "",
                "note": r.note or "",
                "amount": float(r.amount or 0.0),
            })
        return jsonify({"ok": True, "items": items})

    @app.post("/api/reservations")
    @login_required
    def api_create_reservation():
        payload = request.get_json(force=True) or {}
        try:
            when = datetime.strptime(payload["date"], "%Y-%m-%d").date()
            res = Reservation(
                restaurant_id=current_user.restaurant_id,
                date=when,
                time=payload.get("time", "20:00"),
                name=payload.get("name", "").strip(),
                phone=payload.get("phone"),
                people=int(payload.get("people", 2)),
                status=payload.get("status"),
                note=payload.get("note"),
                amount=float(payload.get("amount", 0.0)),
            )
            db.session.add(res)
            db.session.commit()
            return jsonify({"ok": True, "id": res.id})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.put("/api/reservations/<int:res_id>")
    @login_required
    def api_update_reservation(res_id: int):
        payload = request.get_json(force=True) or {}
        r = Reservation.query.filter_by(id=res_id, restaurant_id=current_user.restaurant_id).first_or_404()
        try:
            if "date" in payload:
                r.date = datetime.strptime(payload["date"], "%Y-%m-%d").date()
            if "time" in payload:
                r.time = payload["time"]
            if "name" in payload:
                r.name = payload["name"].strip()
            if "phone" in payload:
                r.phone = payload["phone"]
            if "people" in payload:
                r.people = int(payload["people"])
            if "status" in payload:
                r.status = payload["status"]
            if "note" in payload:
                r.note = payload["note"]
            if "amount" in payload:
                r.amount = float(payload["amount"])
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.delete("/api/reservations/<int:res_id>")
    @login_required
    def api_delete_reservation(res_id: int):
        r = Reservation.query.filter_by(id=res_id, restaurant_id=current_user.restaurant_id).first_or_404()
        try:
            db.session.delete(r)
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # ------------------ API ORARI SETTIMANALI ------------------

    @app.post("/api/hours")
    @login_required
    def api_save_hours():
        """
        body: { "hours": { "0":"12:00-15:00, 19:00-23:00", "1":"..." ... "6":"..." } }
        dove 0=Lun ... 6=Dom. Stringa vuota => CHIUSO.
        """
        payload = request.get_json(force=True) or {}
        hours_map = payload.get("hours") or {}
        try:
            # cancella esistenti
            WeeklyHours.query.filter_by(restaurant_id=current_user.restaurant_id).delete()
            for k, windows in hours_map.items():
                wd = int(k)
                rec = WeeklyHours(
                    restaurant_id=current_user.restaurant_id,
                    weekday=wd,
                    windows=(windows or "").strip()
                )
                db.session.add(rec)
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # ------------------ API GIORNI SPECIALI ------------------

    @app.post("/api/special-days")
    @login_required
    def api_add_special():
        """
        body: { "day":"YYYY-MM-DD", "closed": true/false, "windows":"..." }
        """
        payload = request.get_json(force=True) or {}
        try:
            the_day = datetime.strptime(payload["day"], "%Y-%m-%d").date()
            closed = bool(payload.get("closed", False))
            windows = (payload.get("windows") or "").strip()
            # upsert
            rec = SpecialDay.query.filter_by(
                restaurant_id=current_user.restaurant_id, day=the_day
            ).first()
            if not rec:
                rec = SpecialDay(restaurant_id=current_user.restaurant_id, day=the_day)
            rec.closed = closed
            rec.windows = windows
            db.session.add(rec)
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.delete("/api/special-days/<day>")
    @login_required
    def api_delete_special(day: str):
        try:
            the_day = datetime.strptime(day, "%Y-%m-%d").date()
            rec = SpecialDay.query.filter_by(
                restaurant_id=current_user.restaurant_id, day=the_day
            ).first_or_404()
            db.session.delete(rec)
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # ------------------ API PREZZI & COPERTI (placeholder) ------------------

    @app.get("/api/settings")
    @login_required
    def api_get_settings():
        s = Settings.query.filter_by(restaurant_id=current_user.restaurant_id).first()
        data = {
            "avg_price": float(s.avg_price) if s and s.avg_price is not None else 0.0,
            "seats_cap": int(s.seats_cap) if s and s.seats_cap is not None else 0,
        }
        return jsonify({"ok": True, "settings": data})

    @app.post("/api/settings")
    @login_required
    def api_save_settings():
        payload = request.get_json(force=True) or {}
        try:
            s = Settings.query.filter_by(restaurant_id=current_user.restaurant_id).first()
            if not s:
                s = Settings(restaurant_id=current_user.restaurant_id)
            if "avg_price" in payload:
                s.avg_price = float(payload["avg_price"])
            if "seats_cap" in payload:
                s.seats_cap = int(payload["seats_cap"])
            db.session.add(s)
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # ------------------ API MENU DIGITALE (semplici CRUD) ------------------

    @app.get("/api/menu-items")
    @login_required
    def api_menu_list():
        items = MenuItem.query.filter_by(restaurant_id=current_user.restaurant_id)\
                              .order_by(MenuItem.category.asc(), MenuItem.name.asc()).all()
        return jsonify({"ok": True, "items": [
            {"id": m.id, "name": m.name, "price": float(m.price), "category": m.category or "", "available": bool(m.available)}
            for m in items
        ]})

    @app.post("/api/menu-items")
    @login_required
    def api_menu_create():
        payload = request.get_json(force=True) or {}
        try:
            m = MenuItem(
                restaurant_id=current_user.restaurant_id,
                name=(payload.get("name") or "").strip(),
                price=float(payload.get("price", 0)),
                category=(payload.get("category") or "").strip(),
                available=bool(payload.get("available", True)),
            )
            db.session.add(m)
            db.session.commit()
            return jsonify({"ok": True, "id": m.id})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.put("/api/menu-items/<int:item_id>")
    @login_required
    def api_menu_update(item_id: int):
        payload = request.get_json(force=True) or {}
        m = MenuItem.query.filter_by(id=item_id, restaurant_id=current_user.restaurant_id).first_or_404()
        try:
            if "name" in payload:
                m.name = (payload["name"] or "").strip()
            if "price" in payload:
                m.price = float(payload["price"])
            if "category" in payload:
                m.category = (payload["category"] or "").strip()
            if "available" in payload:
                m.available = bool(payload["available"])
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.delete("/api/menu-items/<int:item_id>")
    @login_required
    def api_menu_delete(item_id: int):
        m = MenuItem.query.filter_by(id=item_id, restaurant_id=current_user.restaurant_id).first_or_404()
        try:
            db.session.delete(m)
            db.session.commit()
            return jsonify({"ok": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 400

    # ------------------ HEALTHCHECK ------------------

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app


# Necessario per gunicorn (app:app)
app = create_app()

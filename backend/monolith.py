from __future__ import annotations
import os, sys, importlib
from datetime import date, datetime, time
from typing import Any, Dict, Optional

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_cors import CORS
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

# =================== MODELS IMPORT ROBUSTO ===================
SpecialDay = None  # type: ignore
WeeklyHour = None  # type: ignore

try:
    from .models import db, Restaurant, User, Reservation  # type: ignore
    try:
        from .models import SpecialDay as _SpecialDay  # type: ignore
        SpecialDay = _SpecialDay
    except Exception:
        pass
    try:
        from .models import WeeklyHour as _WeeklyHour  # type: ignore
        WeeklyHour = _WeeklyHour
    except Exception:
        pass
except Exception:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    models = importlib.import_module("models")
    db = models.db
    Restaurant = models.Restaurant
    User = models.User
    Reservation = models.Reservation
    SpecialDay = getattr(models, "SpecialDay", None)
    WeeklyHour = getattr(models, "WeeklyHour", None)

# =================== HELPERS ===================
def _safe_str(v: Optional[str]) -> str:
    return (v or "").strip()

def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def _parse_time(s: str) -> time:
    return datetime.strptime(s, "%H:%M").time()

def _today() -> date:
    return date.today()

def _reservations_for_day(when: date, restaurant_id: int):
    q = Reservation.query.filter_by(restaurant_id=restaurant_id)
    if hasattr(Reservation, "date"):
        q = q.filter(Reservation.date == when).order_by(
            getattr(Reservation, "time", None) or Reservation.id
        )
        return q
    if hasattr(Reservation, "when"):
        start = datetime.combine(when, time(0, 0))
        end = datetime.combine(when, time(23, 59))
        q = q.filter(Reservation.when >= start, Reservation.when <= end)  # type: ignore[attr-defined]
        return q.order_by(Reservation.when)  # type: ignore[attr-defined]
    return q.order_by(Reservation.id)

def _serialize_res(r) -> Dict[str, Any]:
    if hasattr(r, "date"):
        d: date = getattr(r, "date")
        t: Optional[time] = getattr(r, "time", None)
        hhmm = t.strftime("%H:%M") if isinstance(t, time) else None
        iso = d.isoformat()
    elif hasattr(r, "when"):
        w: datetime = getattr(r, "when")  # type: ignore[assignment]
        iso = w.date().isoformat()
        hhmm = w.strftime("%H:%M")
    else:
        iso = _today().isoformat()
        hhmm = "20:00"

    return {
        "id": r.id,
        "date": iso,
        "time": hhmm,
        "name": getattr(r, "name", ""),
        "phone": getattr(r, "phone", ""),
        "people": getattr(r, "people", 2),
        "status": getattr(r, "status", "pending"),
        "note": getattr(r, "note", ""),
    }

def _apply_payload(r, data: Dict[str, Any]) -> None:
    if "name" in data:
        r.name = _safe_str(data["name"])
    if "phone" in data:
        r.phone = _safe_str(data["phone"])
    if "people" in data:
        r.people = int(data["people"] or 1)
    if "status" in data:
        r.status = _safe_str(data["status"]) or "pending"
    if "note" in data:
        r.note = _safe_str(data["note"])

    if "date" in data:
        d = _parse_date(data["date"])
        if hasattr(r, "date"):
            r.date = d  # type: ignore[attr-defined]
        elif hasattr(r, "when") and "time" in data:
            t = _parse_time(data["time"])
            r.when = datetime.combine(d, t)  # type: ignore[attr-defined]
    if "time" in data:
        t = _parse_time(data["time"])
        if hasattr(r, "time"):
            r.time = t  # type: ignore[attr-defined]
        elif hasattr(r, "when") and "date" in data:
            d = _parse_date(data["date"])
            r.when = datetime.combine(d, t)  # type: ignore[attr-defined]

# =================== APP FACTORY ===================
def _create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-please-change-me")

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        inst = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "instance"))
        os.makedirs(inst, exist_ok=True)
        db_path = os.path.join(inst, "app.db")
        db_url = f"sqlite:///{db_path}"

    app.config.update(SQLALCHEMY_DATABASE_URI=db_url, SQLALCHEMY_TRACK_MODIFICATIONS=False)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(uid: str):
        return User.query.get(int(uid))

    # bootstrap DB
    with app.app_context():
        db.create_all()
        rest = Restaurant.query.first()
        if not rest:
            rest = Restaurant(name="Haru Asian Fusion Restaurant", logo_path="img/logo_sushi.svg")
            db.session.add(rest)
            db.session.commit()

        admin = User.query.filter_by(username="haru_admin").first()
        if not admin:
            admin = User(username="haru_admin", password="Password123!", restaurant_id=rest.id)
            db.session.add(admin)
            db.session.commit()

    # ------------------------ ROUTES HTML ------------------------
    @app.route("/")
    def home():
        return redirect(url_for("dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = _safe_str(request.form.get("username"))
            password = _safe_str(request.form.get("password"))
            remember = bool(request.form.get("remember"))

            user = User.query.filter_by(username=username).first()
            if user and password == getattr(user, "password", ""):
                login_user(user, remember=remember)
                next_url = _safe_str(request.args.get("next")) or url_for("dashboard")
                return redirect(next_url)
            return render_template("login.html", error="Credenziali non valide")

        # login page: passiamo restaurant=None per forzare logo_robot nell'header
        return render_template("login.html", restaurant=None, error=None)

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        rest = Restaurant.query.get(current_user.restaurant_id)
        today = _today()
        if hasattr(Reservation, "date"):
            kpi_today = (
                Reservation.query.filter_by(restaurant_id=current_user.restaurant_id)
                .filter(Reservation.date == today)
                .count()
            )
        else:
            kpi_today = Reservation.query.filter_by(restaurant_id=current_user.restaurant_id).count()

        kpi_income = 0
        return render_template("dashboard.html", restaurant=rest, kpi_today=kpi_today, kpi_income=kpi_income)

    # ------------------------ API RESERVATIONS ------------------------
    @app.route("/api/reservations", methods=["GET"])
    @login_required
    def api_res_list():
        day = request.args.get("date")
        qtext = (request.args.get("q") or "").strip().lower()
        d = _parse_date(day) if day else _today()

        q = _reservations_for_day(d, current_user.restaurant_id)

        # filtro testo su nome/telefono/ora
        if qtext:
            clauses = []
            name_col  = getattr(Reservation, "name", None)
            phone_col = getattr(Reservation, "phone", None)
            time_col  = getattr(Reservation, "time", None)
            if name_col is not None:
                clauses.append(db.func.lower(name_col).contains(qtext))
            if phone_col is not None:
                clauses.append(db.func.lower(phone_col).contains(qtext))
            if time_col is not None:
                clauses.append(db.func.strftime("%H:%M", time_col).contains(qtext))
            if not clauses and hasattr(Reservation, "when"):
                clauses.append(db.func.strftime("%H:%M", getattr(Reservation, "when")).contains(qtext))
            if clauses:
                q = q.filter(db.or_(*clauses))

        items = [_serialize_res(r) for r in q.all()]
        return jsonify(items)

    @app.route("/api/reservations", methods=["POST"])
    @login_required
    def api_res_create():
        data = request.get_json(force=True, silent=True) or {}
        r = Reservation(restaurant_id=current_user.restaurant_id)
        _apply_payload(r, data)
        db.session.add(r)
        db.session.commit()
        return jsonify(_serialize_res(r)), 201

    @app.route("/api/reservations/<int:res_id>", methods=["PATCH"])
    @login_required
    def api_res_update(res_id: int):
        r = Reservation.query.get_or_404(res_id)
        if getattr(r, "restaurant_id", None) != current_user.restaurant_id:
            return jsonify({"error": "forbidden"}), 403
        data = request.get_json(force=True, silent=True) or {}
        _apply_payload(r, data)
        db.session.commit()
        return jsonify(_serialize_res(r))

    @app.route("/api/reservations/<int:res_id>", methods=["DELETE"])
    @login_required
    def api_res_delete(res_id: int):
        r = Reservation.query.get_or_404(res_id)
        if getattr(r, "restaurant_id", None) != current_user.restaurant_id:
            return jsonify({"error": "forbidden"}), 403
        db.session.delete(r)
        db.session.commit()
        return jsonify({"ok": True})

    # ------------------------ API WEEKLY HOURS ------------------------
    @app.route("/api/weekly-hours", methods=["GET"])
    @login_required
    def api_weekly_get():
        rest = Restaurant.query.get(current_user.restaurant_id)
        default = {
            "Lunedì":"12:00-15:00, 19:00-23:00",
            "Martedì":"12:00-15:00, 19:00-23:00",
            "Mercoledì":"12:00-15:00, 19:00-23:00",
            "Giovedì":"12:00-15:00, 19:00-23:00",
            "Venerdì":"12:00-15:00, 19:00-23:00",
            "Sabato":"12:00-15:00, 19:00-23:00",
            "Domenica":"12:00-15:00, 19:00-23:00",
        }
        if hasattr(rest, "weekly_hours_json") and getattr(rest, "weekly_hours_json"):
            import json
            try:
                return jsonify(json.loads(rest.weekly_hours_json))
            except Exception:
                pass
        return jsonify(default)

    @app.route("/api/weekly-hours", methods=["POST"])
    @login_required
    def api_weekly_save():
        rest = Restaurant.query.get(current_user.restaurant_id)
        data = request.get_json(force=True, silent=True) or {}
        if hasattr(rest, "weekly_hours_json"):
            import json
            rest.weekly_hours_json = json.dumps(data, ensure_ascii=False)
            db.session.commit()
        return jsonify({"ok": True})

    # ------------------------ API SPECIAL DAYS ------------------------
    @app.route("/api/special-days", methods=["GET"])
    @login_required
    def api_special_list():
        if SpecialDay is None:
            return jsonify([])
        items = SpecialDay.query.filter_by(restaurant_id=current_user.restaurant_id).all()
        out = []
        for s in items:
            out.append({"date": s.date.isoformat(), "closed": bool(getattr(s, "closed", False)), "windows": getattr(s, "windows", "")})
        return jsonify(out)

    @app.route("/api/special-days", methods=["POST"])
    @login_required
    def api_special_save():
        if SpecialDay is None:
            return jsonify({"ok": True})
        data = request.get_json(force=True, silent=True) or {}
        d = _parse_date(data["date"])
        it = SpecialDay.query.filter_by(restaurant_id=current_user.restaurant_id, date=d).first()
        if not it:
            it = SpecialDay(restaurant_id=current_user.restaurant_id, date=d)
            db.session.add(it)
        it.closed = bool(data.get("closed", False))
        it.windows = _safe_str(data.get("windows", ""))
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/api/special-days", methods=["DELETE"])
    @login_required
    def api_special_delete():
        if SpecialDay is None:
            return jsonify({"ok": True})
        data = request.get_json(force=True, silent=True) or {}
        d = _parse_date(data["date"])
        it = SpecialDay.query.filter_by(restaurant_id=current_user.restaurant_id, date=d).first()
        if it:
            db.session.delete(it)
            db.session.commit()
        return jsonify({"ok": True})

    # ------------------------ API MENU & PREZZI ------------------------
    @app.route("/api/menu-prices", methods=["GET","POST"])
    @login_required
    def api_menu_prices():
        rest = Restaurant.query.get(current_user.restaurant_id)
        import json
        key = "menu_prices_json"   # campo JSON generico sul Restaurant
        current = {}
        if hasattr(rest, key) and getattr(rest, key):
            try:
                current = json.loads(getattr(rest, key))
            except Exception:
                current = {}

        if request.method == "POST":
            data = request.get_json(force=True, silent=True) or {}
            current = {
                "enabled": bool(data.get("enabled")),
                "lunch_price": float(data.get("lunch_price") or 0),
                "dinner_price": float(data.get("dinner_price") or 0),
            }
            setattr(rest, key, json.dumps(current, ensure_ascii=False))
            db.session.commit()
            return jsonify({"ok": True})
        return jsonify(current or {"enabled": False, "lunch_price": 0, "dinner_price": 0})

    return app

app = _create_app()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

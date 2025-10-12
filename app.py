import os
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///local.db")
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"

    with app.app_context():
        _ensure_tables()
        _ensure_demo_seed()

    # -----------------------------------------------------------------------------
    # Pages
    # -----------------------------------------------------------------------------
    @app.route("/", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user, remember=("remember" in request.form))
                return redirect(url_for("dashboard"))
            # login failed → ricarico pagina con errore soft
            return render_template("login.html", error="Credenziali non valide")
        return render_template("login.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        # tema (cookie)
        theme = request.cookies.get("theme", "dark")
        return render_template("dashboard.html", theme=theme)

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    # -----------------------------------------------------------------------------
    # API – Reservations
    # -----------------------------------------------------------------------------
    @app.get("/api/reservations")
    @login_required
    def api_list_reservations():
        d = request.args.get("date")
        q = Reservation.query.filter_by(restaurant_id=current_user.restaurant_id)
        if d:
            try:
                d_obj = datetime.strptime(d, "%Y-%m-%d").date()
                q = q.filter(Reservation.date == d_obj)
            except ValueError:
                return jsonify({"ok": False, "error": "Invalid date"}), 400

        items = q.order_by(Reservation.date.asc(), Reservation.time.asc()).all()
        return jsonify({"ok": True, "items": [r.to_dict() for r in items]})

    @app.post("/api/reservations")
    @login_required
    def api_create_reservation():
        data = request.json or {}
        try:
            d = datetime.strptime(data["date"], "%Y-%m-%d").date()
            t = datetime.strptime(data["time"], "%H:%M").time()
            name = (data.get("name") or "").strip()
            phone = (data.get("phone") or "").strip()
            people = int(data.get("people") or 0)
            status = (data.get("status") or "pending").strip()
            note = (data.get("note") or "").strip()
        except Exception:
            return jsonify({"ok": False, "error": "Dati non validi"}), 400

        r = Reservation(
            restaurant_id=current_user.restaurant_id,
            date=d, time=t, name=name, phone=phone,
            people=people, status=status, note=note
        )
        db.session.add(r)
        db.session.commit()
        return jsonify({"ok": True, "item": r.to_dict()})

    @app.put("/api/reservations/<int:rid>")
    @login_required
    def api_update_reservation(rid):
        r = Reservation.query.filter_by(id=rid, restaurant_id=current_user.restaurant_id).first_or_404()
        data = request.json or {}
        if "date" in data:
            r.date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        if "time" in data:
            r.time = datetime.strptime(data["time"], "%H:%M").time()
        if "name" in data:   r.name = (data["name"] or "").strip()
        if "phone" in data:  r.phone = (data["phone"] or "").strip()
        if "people" in data: r.people = int(data["people"] or 0)
        if "status" in data: r.status = (data["status"] or "pending").strip()
        if "note" in data:   r.note = (data["note"] or "").strip()
        db.session.commit()
        return jsonify({"ok": True, "item": r.to_dict()})

    @app.delete("/api/reservations/<int:rid>")
    @login_required
    def api_delete_reservation(rid):
        r = Reservation.query.filter_by(id=rid, restaurant_id=current_user.restaurant_id).first_or_404()
        db.session.delete(r)
        db.session.commit()
        return jsonify({"ok": True})

    # -----------------------------------------------------------------------------
    # API – Opening hours
    # -----------------------------------------------------------------------------
    @app.post("/api/hours")
    @login_required
    def api_save_hours():
        payload = request.json or {}
        # payload = {"hours": {"mon": "12:00-15:00, 19:00-23:00", ...}}
        hours_map = payload.get("hours") or {}
        # upsert per ciascun day_key
        for day_key, windows in hours_map.items():
            rec = OpeningHours.query.filter_by(restaurant_id=current_user.restaurant_id, day_key=day_key).first()
            if not rec:
                rec = OpeningHours(restaurant_id=current_user.restaurant_id, day_key=day_key, windows=windows or "")
                db.session.add(rec)
            else:
                rec.windows = windows or ""
        db.session.commit()
        return jsonify({"ok": True})

    # -----------------------------------------------------------------------------
    # API – Special days
    # -----------------------------------------------------------------------------
    @app.post("/api/special-days")
    @login_required
    def api_save_special_day():
        data = request.json or {}
        try:
            d = datetime.strptime(data["date"], "%Y-%m-%d").date()
        except Exception:
            return jsonify({"ok": False, "error": "Invalid date"}), 400

        closed_all_day = bool(data.get("closed_all_day") or False)
        windows = (data.get("windows") or "").strip()

        rec = SpecialDay.query.filter_by(restaurant_id=current_user.restaurant_id, date=d).first()
        if not rec:
            rec = SpecialDay(restaurant_id=current_user.restaurant_id, date=d, closed_all_day=closed_all_day, windows=windows)
            db.session.add(rec)
        else:
            rec.closed_all_day = closed_all_day
            rec.windows = windows
        db.session.commit()
        return jsonify({"ok": True})

    # -----------------------------------------------------------------------------
    # Static theme cookie
    # -----------------------------------------------------------------------------
    @app.post("/api/theme")
    @login_required
    def api_set_theme():
        theme = (request.json or {}).get("theme", "dark")
        resp = make_response(jsonify({"ok": True}))
        resp.set_cookie("theme", theme, max_age=60*60*24*365, samesite="Lax")
        return resp

    return app

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, default="Ristorante")

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(60), nullable=True)
    people = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(30), nullable=False, default="pending")
    note = db.Column(db.Text, nullable=True)
    # Colonna opzionale: se non esiste nel DB non viene usata (fallback nel to_dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    def to_dict(self):
        # Fallback se la colonna non c’è nella tabella reale
        created = None
        try:
            created = self.created_at.isoformat() if self.created_at else None
        except Exception:
            created = None
        return {
            "id": self.id,
            "restaurant_id": self.restaurant_id,
            "date": self.date.isoformat(),
            "time": self.time.strftime("%H:%M"),
            "name": self.name,
            "phone": self.phone,
            "people": self.people,
            "status": self.status,
            "note": self.note or "",
            "created_at": created
        }

class OpeningHours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    day_key = db.Column(db.String(10), nullable=False)  # mon, tue, ...
    windows = db.Column(db.String(255), nullable=False, default="")

class SpecialDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    closed_all_day = db.Column(db.Boolean, nullable=False, default=False)
    windows = db.Column(db.String(255), nullable=False, default="")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _ensure_tables():
    """Crea le tabelle mancanti senza toccare quelle esistenti."""
    db.create_all()

def _ensure_demo_seed():
    """Seed minimale per accedere subito: utente haru-admin → Password123!"""
    if not Restaurant.query.first():
        rest = Restaurant(name="Haru Asian Fusion Restaurant")
        db.session.add(rest)
        db.session.commit()
    else:
        rest = Restaurant.query.first()

    if not User.query.filter_by(username="haru-admin").first():
        u = User(
            username="haru-admin",
            password_hash=generate_password_hash("Password123!"),
            restaurant_id=rest.id
        )
        db.session.add(u)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Gunicorn entry
app = create_app()

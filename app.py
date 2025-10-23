import os
from datetime import datetime, date, time as dtime
from typing import Optional
from flask import (
    Flask, render_template, request, redirect,
    url_for, jsonify, flash
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from sqlalchemy import text, inspect
from werkzeug.security import generate_password_hash, check_password_hash


# -----------------------------------------------------------------------------
# CONFIGURAZIONE BASE
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-key")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non impostato!")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# -----------------------------------------------------------------------------
# MODELLI DATABASE
# -----------------------------------------------------------------------------
class Restaurant(db.Model):
    __tablename__ = "restaurant"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    logo_path = db.Column(db.String(255), nullable=False)
    weekly_hours_json = db.Column(db.Text)


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, index=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # legacy (plain)
    password_hash = db.Column(db.String(255))             # nuovo hash
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    def get_id(self):
        return str(self.id)


class Reservation(db.Model):
    __tablename__ = "reservation"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    people = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime)  # bootstrap automatico se manca


class SpecialDay(db.Model):
    __tablename__ = "special_day"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    closed = db.Column(db.Boolean, default=False)
    windows = db.Column(db.Text)


class Settings(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, unique=True)
    avg_price_lunch = db.Column(db.Numeric(asdecimal=False))
    avg_price_dinner = db.Column(db.Numeric(asdecimal=False))
    cover_price = db.Column(db.Numeric(asdecimal=False))
    capacity_max = db.Column(db.Integer)
    min_people = db.Column(db.Integer)


class OpeningHour(db.Model):
    __tablename__ = "opening_hour"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)
    windows = db.Column(db.Text)


# -----------------------------------------------------------------------------
# BOOTSTRAP DELLO SCHEMA
# -----------------------------------------------------------------------------
def _ensure_schema():
    """Controlla che la tabella reservation abbia la colonna created_at."""
    engine = db.get_engine()
    insp = inspect(engine)
    cols = [c["name"] for c in insp.get_columns("reservation")]
    if "created_at" not in cols:
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("ALTER TABLE reservation ADD COLUMN created_at TIMESTAMP DEFAULT NOW()")
                )
        except Exception:
            pass  # la colonna esiste già


# ✅ Flask 3+ non supporta più before_first_request
with app.app_context():
    _ensure_schema()


# -----------------------------------------------------------------------------
# FUNZIONI DI SUPPORTO
# -----------------------------------------------------------------------------
def _parse_date(v: str) -> date:
    v = (v or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError("Data non valida")

def _parse_time(v: str) -> dtime:
    v = (v or "").strip()
    for fmt in ("%H:%M",):
        try:
            return datetime.strptime(v, fmt).time()
        except ValueError:
            continue
    raise ValueError("Orario non valido")

def _map_status(v: str) -> str:
    v = (v or "").upper()
    m = {
        "PENDING": "PENDING", "ATTESA": "PENDING", "IN ATTESA": "PENDING",
        "CONFIRMED": "CONFIRMED", "CONFERMATA": "CONFIRMED",
        "CANCELLED": "CANCELLED", "CANCELLATA": "CANCELLED", "ANNULLATA": "CANCELLED"
    }
    return m.get(v, "PENDING")


# -----------------------------------------------------------------------------
# LOGIN MANAGEMENT
# -----------------------------------------------------------------------------
@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    remember = bool(request.form.get("remember"))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash("Credenziali errate", "error")
        return redirect(url_for("login"))

    ok = False

    # 1️⃣ Se esiste hash → verifica con hash
    if user.password_hash:
        ok = check_password_hash(user.password_hash, password)

    # 2️⃣ Altrimenti controlla la password in chiaro e la migra
    if not ok and user.password == password:
        ok = True
        user.password_hash = generate_password_hash(password)
        user.password = ""
        db.session.commit()

    if not ok:
        flash("Credenziali errate", "error")
        return redirect(url_for("login"))

    login_user(user, remember=remember)
    return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# -----------------------------------------------------------------------------
# DASHBOARD
# -----------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    rest = Restaurant.query.get(current_user.restaurant_id)
    settings = Settings.query.filter_by(restaurant_id=current_user.restaurant_id).first()
    return render_template("dashboard.html", restaurant=rest, settings=settings)


# -----------------------------------------------------------------------------
# API PRENOTAZIONI
# -----------------------------------------------------------------------------
@app.route("/api/reservations", methods=["GET"])
@login_required
def api_reservations_list():
    d = request.args.get("date")
    try:
        the_date = _parse_date(d) if d else date.today()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    q = (Reservation.query
         .filter_by(restaurant_id=current_user.restaurant_id, date=the_date)
         .order_by(Reservation.time.asc()))
    items = [{
        "id": r.id,
        "date": r.date.isoformat(),
        "time": r.time.strftime("%H:%M"),
        "name": r.name,
        "phone": r.phone,
        "people": r.people,
        "status": r.status,
        "note": r.note or ""
    } for r in q.all()]
    return jsonify({"ok": True, "items": items})


@app.route("/api/reservations", methods=["POST"])
@login_required
def api_reservations_create():
    data = request.get_json(silent=True) or {}
    try:
        r = Reservation(
            restaurant_id=current_user.restaurant_id,
            date=_parse_date(data.get("date")),
            time=_parse_time(data.get("time")),
            name=(data.get("name") or "").strip(),
            phone=(data.get("phone") or "").strip(),
            people=int(data.get("people") or 2),
            status=_map_status(data.get("status")),
            note=(data.get("note") or "").strip()
        )
        if not r.name:
            raise ValueError("Nome richiesto")
        db.session.add(r)
        db.session.commit()
        return jsonify({"ok": True, "id": r.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


# -----------------------------------------------------------------------------
# API ORARI E GIORNI SPECIALI
# -----------------------------------------------------------------------------
@app.route("/api/hours", methods=["POST"])
@login_required
def api_hours_save():
    data = request.get_json(silent=True) or {}
    try:
        rid = current_user.restaurant_id
        for k, windows in data.items():
            wd = int(k)
            oh = OpeningHour.query.filter_by(restaurant_id=rid, weekday=wd).first()
            if not oh:
                oh = OpeningHour(restaurant_id=rid, weekday=wd)
                db.session.add(oh)
            oh.windows = (windows or "").strip()
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/special-days", methods=["POST"])
@login_required
def api_special_days_save():
    data = request.get_json(silent=True) or {}
    try:
        rid = current_user.restaurant_id
        d = _parse_date(data.get("date"))
        closed = bool(data.get("closed"))
        windows = (data.get("windows") or "").strip()

        sd = SpecialDay.query.filter_by(restaurant_id=rid, date=d).first()
        if not sd:
            sd = SpecialDay(restaurant_id=rid, date=d)
            db.session.add(sd)
        sd.closed = closed
        sd.windows = windows
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


# -----------------------------------------------------------------------------
# API SETTINGS
# -----------------------------------------------------------------------------
@app.route("/api/settings", methods=["POST"])
@login_required
def api_settings_save():
    data = request.get_json(silent=True) or {}
    try:
        rid = current_user.restaurant_id
        s = Settings.query.filter_by(restaurant_id=rid).first()
        if not s:
            s = Settings(restaurant_id=rid)
            db.session.add(s)

        def _num(x):
            if not x: return None
            return float(str(x).replace(",", "."))
        def _int(x):
            if not x: return None
            return int(x)

        s.avg_price_lunch = _num(data.get("avg_price_lunch"))
        s.avg_price_dinner = _num(data.get("avg_price_dinner"))
        s.cover_price = _num(data.get("cover_price"))
        s.capacity_max = _int(data.get("capacity_max"))
        s.min_people = _int(data.get("min_people"))

        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


# -----------------------------------------------------------------------------
# ERROR HANDLERS
# -----------------------------------------------------------------------------
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"ok": False, "error": "bad_request"}), 400

@app.errorhandler(500)
def server_error(e):
    return jsonify({"ok": False, "error": "server_error"}), 500


# -----------------------------------------------------------------------------
# MAIN (per test locale)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        _ensure_schema()
    app.run(host="0.0.0.0", port=5000, debug=True)

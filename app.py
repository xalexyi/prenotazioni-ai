import os
from datetime import datetime, date, time as dtime
from typing import Dict, Any, Optional

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy import text, inspect
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non impostato")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# -----------------------------------------------------------------------------
# MODELS (basati sullo schema che hai su Render)
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
    password = db.Column(db.String(255), nullable=False)  # legacy plain text (verrà rimosso alla prima login)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    password_hash = db.Column(db.String(255))  # nuovo

    # Flask-Login
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
    created_at = db.Column(db.DateTime)  # può mancare nel DB vecchio (bootstrap sotto)


class SpecialDay(db.Model):
    __tablename__ = "special_day"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    closed = db.Column(db.Boolean, nullable=False, default=False)
    windows = db.Column(db.Text)  # es: "12:00-15:00, 19:00-22:30"


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
    weekday = db.Column(db.Integer, nullable=False)  # 1=Lun ... 7=Dom
    windows = db.Column(db.Text)  # "12:00-15:00, 19:00-23:00"


# -----------------------------------------------------------------------------
# Bootstrap schema idempotente (non rompe nulla)
# -----------------------------------------------------------------------------

def _ensure_schema():
    engine = db.get_engine()
    insp = inspect(engine)

    # Aggiungi colonna created_at su reservation se manca
    cols = [c["name"] for c in insp.get_columns("reservation")]
    if "created_at" not in cols:
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reservation ADD COLUMN created_at TIMESTAMP DEFAULT NOW()"))
        except Exception:
            # già aggiunta altrove o race condition: ignora
            pass


@app.before_first_request
def _on_boot():
    _ensure_schema()


# -----------------------------------------------------------------------------
# Helpers parsing e mapping
# -----------------------------------------------------------------------------

def _parse_date(value: str) -> date:
    value = (value or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError("Data non valida")

def _parse_time(value: str) -> dtime:
    value = (value or "").strip()
    for fmt in ("%H:%M",):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError("Orario non valido")

def _map_status(value: str) -> str:
    v = (value or "").strip().upper()
    aliases = {
        "PENDING": "PENDING",
        "ATTESA": "PENDING",
        "IN ATTESA": "PENDING",
        "CONFIRMED": "CONFIRMED",
        "CONFERMATA": "CONFIRMED",
        "CANCELLATA": "CANCELLED",
        "CANCELLED": "CANCELLED",
        "ANNULLATA": "CANCELLED",
    }
    return aliases.get(v, "PENDING")


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    remember = bool(request.form.get("remember"))

    if not username or not password:
        flash("Inserisci username e password", "error")
        return redirect(url_for("login"))

    user = User.query.filter_by(username=username).first()

    # Se non c'è l'utente: errore
    if not user:
        flash("Credenziali errate", "error")
        return redirect(url_for("login"))

    ok = False

    # 1) se esiste hash -> verifica con hash
    if user.password_hash:
        ok = check_password_hash(user.password_hash, password)

    # 2) altrimenti confronta il campo legacy in chiaro e, se matcha, migra ad hash
    if not ok and user.password:
        if user.password == password:
            ok = True
            user.password_hash = generate_password_hash(password)
            # opzionale: svuoto la password legacy
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
# Views
# -----------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    # Info breadcrumb e toggle
    rest = Restaurant.query.get(current_user.restaurant_id)
    settings = Settings.query.filter_by(restaurant_id=current_user.restaurant_id).first()
    return render_template(
        "dashboard.html",
        restaurant=rest,
        settings=settings,
    )


# -----------------------------------------------------------------------------
# API
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
         .order_by(Reservation.date.asc(), Reservation.time.asc()))
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
            note=(data.get("note") or "").strip(),
        )
        if not r.name:
            raise ValueError("Nome richiesto")
        db.session.add(r)
        db.session.commit()
        return jsonify({"ok": True, "id": r.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/hours", methods=["POST"])
@login_required
def api_hours_save():
    """
    Body atteso:
    {
      "1": "12:00-15:00, 19:00-23:00",
      "2": "...",
      ...
      "7": "..."
    }
    """
    payload = request.get_json(silent=True) or {}
    try:
        rid = current_user.restaurant_id
        # sovrascrivo/setto uno per uno
        for wd_str, windows in payload.items():
            try:
                wd = int(wd_str)
            except:
                continue
            oh = OpeningHour.query.filter_by(restaurant_id=rid, weekday=wd).first()
            if not oh:
                oh = OpeningHour(restaurant_id=rid, weekday=wd, windows=(windows or "").strip())
                db.session.add(oh)
            else:
                oh.windows = (windows or "").strip()
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/special-days", methods=["POST"])
@login_required
def api_special_days_save():
    """
    Body atteso:
    {
      "date": "YYYY-MM-DD" o "DD/MM/YYYY",
      "closed": true/false,
      "windows": "12:00-15:00, 19:00-22:30"
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        rid = current_user.restaurant_id
        d = _parse_date(data.get("date"))
        closed = bool(data.get("closed"))
        windows = (data.get("windows") or "").strip()

        sd = SpecialDay.query.filter_by(restaurant_id=rid, date=d).first()
        if not sd:
            sd = SpecialDay(restaurant_id=rid, date=d, closed=closed, windows=windows)
            db.session.add(sd)
        else:
            sd.closed = closed
            sd.windows = windows
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/api/settings", methods=["POST"])
@login_required
def api_settings_save():
    """
    Body atteso:
    {
      "avg_price_lunch": "25.0",
      "avg_price_dinner": "30.0",
      "cover_price": "2.5",
      "capacity_max": 60,
      "min_people": 1
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        rid = current_user.restaurant_id
        s = Settings.query.filter_by(restaurant_id=rid).first()
        if not s:
            s = Settings(restaurant_id=rid)
            db.session.add(s)
        # parse numeri in modo safe
        def _num(x): 
            if x is None or str(x).strip() == "": return None
            return float(str(x).replace(",", "."))
        def _int(x):
            if x is None or str(x).strip() == "": return None
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
# Error helpers (JSON comodi per debug front)
# -----------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"ok": False, "error": "bad_request"}), 400

@app.errorhandler(500)
def server_error(e):
    return jsonify({"ok": False, "error": "server_error"}), 500


# -----------------------------------------------------------------------------
# Main (utile in locale)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    with app.app_context():
        _ensure_schema()
    app.run(host="0.0.0.0", port=5000, debug=True)

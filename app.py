import os
import logging
from datetime import datetime, date, time as dtime
from typing import Optional, Dict, Any

from flask import (
    Flask, render_template, request, redirect, url_for, jsonify, session
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect
from sqlalchemy.exc import ProgrammingError, OperationalError, IntegrityError
from flask_cors import CORS
from flask_login import (
    LoginManager, login_user, login_required, logout_user,
    current_user, UserMixin
)

# -------------------------------------------------
# Config base
# -------------------------------------------------
def _bool(v: Optional[str], default=False) -> bool:
    if v is None:
        return default
    return str(v).lower().strip() in {"1", "true", "yes", "y", "on"}

APP_ENV = os.getenv("FLASK_ENV", "production")
DEBUG = _bool(os.getenv("DEBUG"), APP_ENV != "production")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non impostato")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

login_manager = LoginManager(app)
login_manager.login_view = "login"

logging.basicConfig(level=logging.INFO if not DEBUG else logging.DEBUG)
log = logging.getLogger("prenotazioni")

# -------------------------------------------------
# Modelli
# -------------------------------------------------
class Restaurant(db.Model):
    __tablename__ = "restaurant"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    # impostazioni condivise
    avg_price = db.Column(db.Numeric(10, 2), nullable=True)
    cover_price = db.Column(db.Numeric(10, 2), nullable=True)
    capacity_max = db.Column(db.Integer, nullable=True)
    min_people = db.Column(db.Integer, nullable=True)

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    restaurant = db.relationship(Restaurant)

class Reservation(db.Model):
    __tablename__ = "reservation"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    time = db.Column(db.Time, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    people = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default="PENDING")  # PENDING/CONFIRMED/CANCELLED
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=text("NOW()"), nullable=False)

class OpeningHour(db.Model):
    __tablename__ = "opening_hour"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False)  # 0=Mon .. 6=Sun
    windows = db.Column(db.String(255), nullable=True)  # es "12:00-15:00, 19:00-22:30"

class SpecialDay(db.Model):
    __tablename__ = "special_day"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, index=True)
    thedate = db.Column(db.Date, nullable=False, index=True)
    is_closed = db.Column(db.Boolean, nullable=False, default=False)
    windows = db.Column(db.String(255), nullable=True)  # se non chiuso

class MenuItem(db.Model):
    __tablename__ = "menu_item"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None

def _ensure_schema() -> None:
    """
    Bootstrap idempotente che aggiunge colonne mancate senza rompere nulla.
    """
    try:
        engine = db.get_engine()
        insp = inspect(engine)

        # 1) reservation.created_at
        cols = [c["name"] for c in insp.get_columns("reservation")]
        if "created_at" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reservation ADD COLUMN created_at TIMESTAMP DEFAULT NOW()"))
                conn.commit()

    except ProgrammingError:
        # table non ancora create => primo avvio: ok
        pass
    except Exception as e:
        log.warning("ensure_schema warning: %s", e)

def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        # consentiamo anche formati tipo 11/10/2025 (it-IT)
        try:
            return datetime.strptime(s.strip(), "%d/%m/%Y").date()
        except ValueError:
            raise ValueError("Formato data non valido. Usa YYYY-MM-DD oppure DD/MM/YYYY")

def _parse_time(s: str) -> dtime:
    try:
        return datetime.strptime(s.strip(), "%H:%M").time()
    except ValueError:
        raise ValueError("Formato ora non valido. Usa HH:MM")

def _ok(data: Dict[str, Any] = None, code=200):
    if data is None:
        data = {}
    return jsonify({"ok": True, **data}), code

def _err(msg: str, code=400):
    return jsonify({"ok": False, "error": msg}), code

def _restaurant_id() -> int:
    if not current_user.is_authenticated:
        raise RuntimeError("Non autenticato")
    return current_user.restaurant_id

def _reservation_to_json(r: Reservation) -> Dict[str, Any]:
    return {
        "id": r.id,
        "date": r.date.isoformat(),
        "time": r.time.strftime("%H:%M"),
        "name": r.name,
        "phone": r.phone or "",
        "people": r.people,
        "status": r.status,
        "note": r.note or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

# -------------------------------------------------
# Routes HTML
# -------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    _ensure_schema()
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not username or not password:
            return render_template("login.html", error="Inserisci username e password")

        user = User.query.filter_by(username=username).first()
        if not user or user.password_hash != password:
            # Nota: se usi hash reali, sostituisci con check_password_hash()
            return render_template("login.html", error="Credenziali errate")

        login_user(user, remember=bool(request.form.get("remember") == "on"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

# -------------------------------------------------
# API — Prenotazioni
# -------------------------------------------------
@app.route("/api/reservations", methods=["GET"])
@login_required
def api_list_reservations():
    try:
        rid = _restaurant_id()

        qdate_str = request.args.get("date")
        if not qdate_str:
            return _err("Parametro 'date' mancante")

        d = _parse_date(qdate_str)

        qs = (
            Reservation.query
            .filter(Reservation.restaurant_id == rid, Reservation.date == d)
            .order_by(Reservation.date.asc(), Reservation.time.asc())
        )
        items = [_reservation_to_json(x) for x in qs.all()]
        return _ok({"items": items})
    except Exception as e:
        log.exception("Errore /api/reservations GET")
        return _err(str(e), 500)

@app.route("/api/reservations", methods=["POST"])
@login_required
def api_create_reservation():
    try:
        rid = _restaurant_id()
        data = request.get_json(force=True, silent=False) or {}

        date_str = (data.get("date") or "").strip()
        time_str = (data.get("time") or "").strip()
        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()
        status = (data.get("status") or "PENDING").strip().upper()
        note = (data.get("note") or "").strip()
        people = int(data.get("people") or 2)

        if not date_str or not time_str or not name:
            return _err("Campi obbligatori: data, ora, nome")

        d = _parse_date(date_str)
        t = _parse_time(time_str)

        r = Reservation(
            restaurant_id=rid, date=d, time=t, name=name,
            phone=phone, people=people, status=status, note=note,
        )
        db.session.add(r)
        db.session.commit()
        return _ok({"item": _reservation_to_json(r)}, 201)

    except (ValueError, AssertionError) as ve:
        return _err(str(ve), 400)
    except IntegrityError as ie:
        db.session.rollback()
        return _err("Errore integrità dati: " + str(ie.orig)), 400
    except Exception as e:
        db.session.rollback()
        log.exception("Errore /api/reservations POST")
        return _err("Errore server: " + str(e), 500)

@app.route("/api/reservations/<int:res_id>", methods=["DELETE"])
@login_required
def api_delete_reservation(res_id: int):
    try:
        rid = _restaurant_id()
        r = Reservation.query.filter_by(id=res_id, restaurant_id=rid).first()
        if not r:
            return _err("Prenotazione non trovata", 404)
        db.session.delete(r)
        db.session.commit()
        return _ok()
    except Exception as e:
        db.session.rollback()
        log.exception("Errore DELETE reservation")
        return _err(str(e), 500)

# -------------------------------------------------
# API — Orari settimanali
# -------------------------------------------------
@app.route("/api/hours", methods=["GET"])
@login_required
def api_get_hours():
    rid = _restaurant_id()
    items = OpeningHour.query.filter_by(restaurant_id=rid).order_by(OpeningHour.weekday.asc()).all()
    payload = [{"weekday": x.weekday, "windows": x.windows or ""} for x in items]
    return _ok({"items": payload})

@app.route("/api/hours", methods=["POST"])
@login_required
def api_save_hours():
    try:
        rid = _restaurant_id()
        data = request.get_json(force=True) or {}
        items = data.get("items") or []
        if not isinstance(items, list):
            return _err("Formato non valido: items dev'essere lista")

        # upsert 7 righe (0..6). Se non c'è, la creo
        exists = {x.weekday: x for x in OpeningHour.query.filter_by(restaurant_id=rid).all()}
        for raw in items:
            wd = int(raw.get("weekday"))
            windows = (raw.get("windows") or "").strip()
            rec = exists.get(wd)
            if not rec:
                rec = OpeningHour(restaurant_id=rid, weekday=wd, windows=windows)
                db.session.add(rec)
            else:
                rec.windows = windows

        db.session.commit()
        return _ok()
    except Exception as e:
        db.session.rollback()
        log.exception("Errore salvataggio orari")
        return _err(str(e), 500)

# -------------------------------------------------
# API — Giorni speciali
# -------------------------------------------------
@app.route("/api/special-days", methods=["POST"])
@login_required
def api_save_special_day():
    try:
        rid = _restaurant_id()
        data = request.get_json(force=True) or {}
        date_str = (data.get("date") or "").strip()
        is_closed = bool(data.get("is_closed"))
        windows = (data.get("windows") or "").strip()

        d = _parse_date(date_str)

        rec = SpecialDay.query.filter_by(restaurant_id=rid, thedate=d).first()
        if not rec:
            rec = SpecialDay(restaurant_id=rid, thedate=d)
            db.session.add(rec)

        rec.is_closed = is_closed
        rec.windows = "" if is_closed else windows

        db.session.commit()
        return _ok()
    except Exception as e:
        db.session.rollback()
        log.exception("Errore salvataggio giorno speciale")
        return _err(str(e), 500)

# -------------------------------------------------
# API — Prezzi base ristorante
# -------------------------------------------------
@app.route("/api/prices", methods=["GET"])
@login_required
def api_prices_get():
    rid = _restaurant_id()
    r = Restaurant.query.get(rid)
    if not r:
        return _err("Ristorante non trovato", 404)
    return _ok({
        "avg_price": float(r.avg_price) if r.avg_price is not None else None,
        "cover_price": float(r.cover_price) if r.cover_price is not None else None,
        "capacity_max": r.capacity_max,
        "min_people": r.min_people
    })

@app.route("/api/prices", methods=["POST"])
@login_required
def api_prices_save():
    try:
        rid = _restaurant_id()
        r = Restaurant.query.get(rid)
        if not r:
            return _err("Ristorante non trovato", 404)

        data = request.get_json(force=True) or {}
        def _num(x): 
            if x in (None, "", "null"): 
                return None
            return float(x)

        r.avg_price = _num(data.get("avg_price"))
        r.cover_price = _num(data.get("cover_price"))
        r.capacity_max = int(data.get("capacity_max") or 0) or None
        r.min_people = int(data.get("min_people") or 0) or None
        db.session.commit()
        return _ok()
    except Exception as e:
        db.session.rollback()
        log.exception("Errore salvataggio prezzi")
        return _err(str(e), 500)

# -------------------------------------------------
# API — Menu (lista semplice voce-prezzo)
# -------------------------------------------------
@app.route("/api/menu", methods=["GET"])
@login_required
def api_menu_get():
    rid = _restaurant_id()
    rows = MenuItem.query.filter_by(restaurant_id=rid).order_by(MenuItem.id.asc()).all()
    return _ok({"items": [{"id": x.id, "name": x.name, "price": float(x.price)} for x in rows]})

@app.route("/api/menu", methods=["POST"])
@login_required
def api_menu_save():
    try:
        rid = _restaurant_id()
        data = request.get_json(force=True) or {}
        items = data.get("items") or []
        if not isinstance(items, list):
            return _err("Formato non valido: items dev'essere lista")

        # Politica semplice: wipe & replace
        MenuItem.query.filter_by(restaurant_id=rid).delete()
        for it in items:
            name = (it.get("name") or "").strip()
            price = float(it.get("price") or 0)
            if name:
                db.session.add(MenuItem(restaurant_id=rid, name=name, price=price))
        db.session.commit()
        return _ok()
    except Exception as e:
        db.session.rollback()
        log.exception("Errore salvataggio menu")
        return _err(str(e), 500)

# -------------------------------------------------
# Avvio
# -------------------------------------------------
with app.app_context():
    db.create_all()
    _ensure_schema()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=DEBUG)

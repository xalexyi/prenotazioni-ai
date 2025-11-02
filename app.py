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


# -------------------------------------------------------------------------
# CONFIGURAZIONE BASE
# -------------------------------------------------------------------------
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


# -------------------------------------------------------------------------
# MODELLI DATABASE
# -------------------------------------------------------------------------
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
    password = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255))
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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


# -------------------------------------------------------------------------
# BOOTSTRAP SCHEMA (Render non supporta before_first_request)
# -------------------------------------------------------------------------
def _ensure_schema():
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
            pass


with app.app_context():
    _ensure_schema()


# -------------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------------
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
        "PENDING": "PENDING", "ATTESA": "PENDING",
        "CONFIRMED": "CONFIRMED", "CONFERMATA": "CONFIRMED",
        "CANCELLED": "CANCELLED", "CANCELLATA": "CANCELLED"
    }
    return m.get(v, "PENDING")


# -------------------------------------------------------------------------
# LOGIN
# -------------------------------------------------------------------------
@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    user = User.query.filter_by(username=username).first()
    if not user:
        flash("Credenziali errate", "error")
        return redirect(url_for("login"))

    ok = False

    if user.password_hash:
        ok = check_password_hash(user.password_hash, password)
    elif user.password == password:
        ok = True
        user.password_hash = generate_password_hash(password)
        user.password = ""
        db.session.commit()

    if not ok:
        flash("Credenziali errate", "error")
        return redirect(url_for("login"))

    login_user(user)
    return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# -------------------------------------------------------------------------
# DASHBOARD
# -------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    rest = Restaurant.query.get(current_user.restaurant_id)
    settings = Settings.query.filter_by(restaurant_id=current_user.restaurant_id).first()
    return render_template("dashboard.html", restaurant=rest, settings=settings)


# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        _ensure_schema()
    app.run(host="0.0.0.0", port=10000, debug=False)

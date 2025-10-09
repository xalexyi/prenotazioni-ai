# backend/models.py
from __future__ import annotations

from datetime import date, time
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class Restaurant(db.Model):
    __tablename__ = "restaurant"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    logo_path = db.Column(db.String(255), nullable=False, default="img/logo_robot.svg")

    # opzionale: dove salviamo gli orari settimanali in JSON (stringa)
    weekly_hours_json = db.Column(db.Text, nullable=True)

    users = db.relationship("User", backref="restaurant", lazy=True)
    reservations = db.relationship("Reservation", backref="restaurant", lazy=True)

    def __repr__(self) -> str:  # debug
        return f"<Restaurant {self.id} {self.name!r}>"


class User(db.Model, UserMixin):
    """
    User compatibile con Flask-Login grazie a UserMixin:
    - is_authenticated
    - is_active
    - is_anonymous
    - get_id()
    """
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    def __repr__(self) -> str:  # debug
        return f"<User {self.id} {self.username!r}>"


class Reservation(db.Model):
    """
    Usiamo lo schema 'data' + 'ora' per massima compatibilità.
    (Il backend che ti ho dato gestisce sia 'date/time' sia un ipotetico campo 'when'.)
    """
    __tablename__ = "reservation"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    # Info cliente
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=True)

    people = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default="pending")
    note = db.Column(db.String(255), nullable=True)

    # Data & ora (schema usato dalla dashboard)
    date = db.Column(db.Date, nullable=False, default=date.today)
    time = db.Column(db.Time, nullable=True)  # opzionale

    def __repr__(self) -> str:  # debug
        return f"<Reservation {self.id} {self.date} {self.time} {self.name!r}>"


# --- Modelli opzionali: il backend funziona anche senza, ma li includo per completezza. ---

class SpecialDay(db.Model):
    """
    Giorni speciali/chiusure. Il backend li usa se esistono,
    altrimenti ignora gli endpoint senza errori.
    """
    __tablename__ = "special_day"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    date = db.Column(db.Date, nullable=False)
    closed = db.Column(db.Boolean, nullable=False, default=False)
    windows = db.Column(db.String(255), nullable=True)  # es: "18:00-23:00, 12:00-15:00"

    def __repr__(self) -> str:
        return f"<SpecialDay {self.date} closed={self.closed}>"


class WeeklyHour(db.Model):
    """
    Se preferisci salvare gli orari settimanali normalizzati per giorno.
    Non è obbligatorio perché esiste anche weekly_hours_json su Restaurant.
    """
    __tablename__ = "weekly_hour"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    # 0=Lunedì ... 6=Domenica
    weekday = db.Column(db.Integer, nullable=False)
    windows = db.Column(db.String(255), nullable=True)  # es: "12:00-15:00, 19:00-23:00"

    __table_args__ = (
        db.UniqueConstraint("restaurant_id", "weekday", name="uq_restaurant_weekday"),
    )

    def __repr__(self) -> str:
        return f"<WeeklyHour {self.weekday} {self.windows!r}>"
# --- ActiveCall model (aggiungi in fondo a models.py) ---
from sqlalchemy import func
from datetime import timedelta

# importa 'db' dal tuo progetto senza rompere gli import
try:
    from backend import db  # se hai db in backend/__init__.py
except Exception:
    try:
        from app import db  # se inizializzi db in app.py
    except Exception:
        from . import db    # fallback se models.py è in un package

class ActiveCall(db.Model):
    __tablename__ = "active_calls"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, nullable=False, index=True)
    call_sid = db.Column(db.String, nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    @staticmethod
    def cleanup(ttl_minutes: int = 10):
        """Fail-safe: disattiva chiamate troppo vecchie per evitare slot bloccati."""
        cutoff = func.now() - timedelta(minutes=ttl_minutes)
        (db.session.query(ActiveCall)
         .filter(ActiveCall.active.is_(True), ActiveCall.created_at < cutoff)
         .update({ActiveCall.active: False}, synchronize_session=False))
        db.session.commit()

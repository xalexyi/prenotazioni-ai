"""
Modelli SQLAlchemy per Prenotazioni-AI.
Compatibili con PostgreSQL (Render) e SQLite (locale).
"""

from __future__ import annotations
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

from app import db


# =============================================================================
#  MODEL: Restaurant
# =============================================================================

class Restaurant(db.Model):
    __tablename__ = "restaurant"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    logo_path = db.Column(db.String(255))
    weekly_hours_json = db.Column(db.Text)  # fallback legacy

    # relationships
    users = db.relationship("User", backref="restaurant", lazy=True)
    reservations = db.relationship("Reservation", backref="restaurant", lazy=True)
    settings = db.relationship("Settings", backref="restaurant", uselist=False, lazy=True)
    opening_hours = db.relationship("OpeningHours", backref="restaurant", lazy=True)
    special_days = db.relationship("SpecialDay", backref="restaurant", lazy=True)

    def __repr__(self):
        return f"<Restaurant {self.id} {self.name}>"


# =============================================================================
#  MODEL: User
# =============================================================================

class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    def __repr__(self):
        return f"<User {self.username} (rest_id={self.restaurant_id})>"


# =============================================================================
#  MODEL: Reservation
# =============================================================================

class Reservation(db.Model):
    __tablename__ = "reservation"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    people = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(50), default="Confermata")  # Confermata / Annullata / In attesa
    note = db.Column(db.Text)
    date = db.Column(db.String(10), nullable=False)  # "YYYY-MM-DD"
    time = db.Column(db.String(5), nullable=False)   # "HH:MM"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Reservation {self.id} {self.name} {self.date} {self.time}>"


# =============================================================================
#  MODEL: OpeningHours (orari settimanali)
# =============================================================================

class OpeningHours(db.Model):
    __tablename__ = "opening_hours"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0 = Lunedì
    windows = db.Column(db.String(255), nullable=True)  # "12:00-15:00, 19:00-22:30"

    def __repr__(self):
        return f"<OpeningHours rest={self.restaurant_id} dow={self.day_of_week}>"


# =============================================================================
#  MODEL: SpecialDay (giorni speciali / ferie)
# =============================================================================

class SpecialDay(db.Model):
    __tablename__ = "special_day"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    date = db.Column(db.String(10), nullable=False)  # "YYYY-MM-DD"
    closed = db.Column(db.Boolean, default=False)
    windows = db.Column(db.String(255))  # es: "12:00-15:00, 19:00-23:00"

    def __repr__(self):
        return f"<SpecialDay {self.date} closed={self.closed}>"


# =============================================================================
#  MODEL: Settings (prezzi, coperti, menu digitale)
# =============================================================================

class Settings(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, unique=True)

    avg_price = db.Column(db.Float)
    cover = db.Column(db.Float)
    seats_cap = db.Column(db.Integer)
    min_people = db.Column(db.Integer)

    menu_url = db.Column(db.String(255))
    menu_desc = db.Column(db.Text)

    def __repr__(self):
        return f"<Settings rest={self.restaurant_id} avg={self.avg_price}>"


# =============================================================================
#  MODEL: MenuItem (piatti personalizzabili)
# =============================================================================

class MenuItem(db.Model):
    __tablename__ = "menu_item"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<MenuItem {self.name} €{self.price}>"


# =============================================================================
#  MODEL: ActiveCalls (per AI/Voce)
# =============================================================================

class ActiveCall(db.Model):
    __tablename__ = "active_calls"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    call_sid = db.Column(db.String(64), unique=True, nullable=False)
    customer_phone = db.Column(db.String(40))
    status = db.Column(db.String(30), default="active")  # active / closed / error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ActiveCall {self.call_sid} ({self.status})>"


# =============================================================================
#  MODEL: Backup/Logs (opzionale)
# =============================================================================

class SystemLog(db.Model):
    __tablename__ = "system_log"

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(120))
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SystemLog {self.event}>"

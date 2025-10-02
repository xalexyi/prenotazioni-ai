# -*- coding: utf-8 -*-
# backend/models.py
from __future__ import annotations

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


# ===========================
# Account / autenticazione
# ===========================
class Restaurant(UserMixin, db.Model):
    __tablename__ = "restaurants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="Ristorante")
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255))
    logo = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<Restaurant id={self.id} name={self.name!r}>"


# ===========================
# Prenotazioni
# ===========================
class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)

    # coerente con il tuo frontend
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(60), nullable=True)

    # usiamo stringhe, come la tua SQL, non tipi Date/Time per compatibilità
    date = db.Column(db.String(10), nullable=False)   # "YYYY-MM-DD"
    time = db.Column(db.String(5), nullable=False)    # "HH:MM"

    party_size = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default="confirmed")  # confirmed|pending|cancelled
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ===========================
# Orari settimanali ricorrenti
# ===========================
class OpeningHour(db.Model):
    __tablename__ = "opening_hours"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False)            # 0=Mon .. 6=Sun
    start_time = db.Column(db.String(5), nullable=False)       # "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)         # "HH:MM"

    __table_args__ = (
        db.Index("idx_opening_weekday_rest", "restaurant_id", "weekday"),
    )


# ===========================
# Giorni speciali
# ===========================
class SpecialDay(db.Model):
    __tablename__ = "special_days"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    date = db.Column(db.String(10), nullable=False, index=True)  # "YYYY-MM-DD"
    is_closed = db.Column(db.Boolean, nullable=False, default=False)
    start_time = db.Column(db.String(5), nullable=True)
    end_time = db.Column(db.String(5), nullable=True)

    __table_args__ = (
        db.Index("idx_special_date_rest", "restaurant_id", "date"),
    )


# ===========================
# Impostazioni per ristorante
# ===========================
class RestaurantSetting(db.Model):
    __tablename__ = "restaurant_settings"

    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), primary_key=True)
    tz = db.Column(db.String(64), nullable=True)                 # es. "Europe/Rome"
    slot_step_min = db.Column(db.Integer, nullable=True)         # 15/30...
    last_order_min = db.Column(db.Integer, nullable=True)        # minuti prima della chiusura
    min_party = db.Column(db.Integer, nullable=True)
    max_party = db.Column(db.Integer, nullable=True)
    capacity_per_slot = db.Column(db.Integer, nullable=True)

# -*- coding: utf-8 -*-
# backend/models.py — Modelli DB + alias retro-compatibili
from __future__ import annotations

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.orm import synonym

db = SQLAlchemy()


class Restaurant(UserMixin, db.Model):
    __tablename__ = "restaurants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="Ristorante")
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255))
    logo = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self) -> str:
        return str(self.id)

    def __repr__(self) -> str:
        return f"<Restaurant id={self.id} name={self.name!r}>"


class Reservation(db.Model):
    """
    N.B. molti file del progetto usano i nomi 'name', 'phone', 'people'.
    Qui usiamo le colonne canoniche 'customer_name', 'customer_phone', 'party_size'
    ma esponiamo i sinonimi ORM per piena compatibilità in query/filtri.
    """
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(
        db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True
    )

    # Colonne canoniche
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(60))

    # Date/ora come stringhe per compatibilità con JS ("YYYY-MM-DD", "HH:MM")
    date = db.Column(db.String(10), nullable=False)
    time = db.Column(db.String(5), nullable=False)

    party_size = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default="confirmed")
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # ---- Sinonimi ORM (usabili anche nei filtri SQLAlchemy) ----
    # Esempio: Reservation.query.filter(Reservation.phone.ilike("%123%"))
    name = synonym("customer_name")
    phone = synonym("customer_phone")
    people = synonym("party_size")

    def __repr__(self) -> str:
        return f"<Reservation id={self.id} {self.date} {self.time} name={self.customer_name!r}>"


class OpeningHour(db.Model):
    __tablename__ = "opening_hours"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(
        db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True
    )
    weekday = db.Column(db.Integer, nullable=False)        # 0=Mon .. 6=Sun
    start_time = db.Column(db.String(5), nullable=False)   # "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)     # "HH:MM"

    __table_args__ = (
        db.Index("idx_opening_weekday_rest", "restaurant_id", "weekday"),
    )

    def __repr__(self) -> str:
        return f"<OpeningHour rid={self.restaurant_id} wd={self.weekday} {self.start_time}-{self.end_time}>"


class SpecialDay(db.Model):
    __tablename__ = "special_days"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(
        db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True
    )
    date = db.Column(db.String(10), nullable=False, index=True)   # "YYYY-MM-DD"
    is_closed = db.Column(db.Boolean, nullable=False, default=False)
    start_time = db.Column(db.String(5))  # facoltativi se is_closed=True
    end_time = db.Column(db.String(5))

    __table_args__ = (
        db.Index("idx_special_date_rest", "restaurant_id", "date"),
    )

    def __repr__(self) -> str:
        flag = "CLOSED" if self.is_closed else f"{self.start_time}-{self.end_time}"
        return f"<SpecialDay rid={self.restaurant_id} {self.date} {flag}>"


class RestaurantSetting(db.Model):
    __tablename__ = "restaurant_settings"

    restaurant_id = db.Column(
        db.Integer, db.ForeignKey("restaurants.id"), primary_key=True
    )
    tz = db.Column(db.String(64))
    slot_step_min = db.Column(db.Integer)
    last_order_min = db.Column(db.Integer)
    min_party = db.Column(db.Integer)
    max_party = db.Column(db.Integer)
    capacity_per_slot = db.Column(db.Integer)

    def __repr__(self) -> str:
        return f"<RestaurantSetting rid={self.restaurant_id} tz={self.tz!r}>"

# --------------------------------------------------------------------
# Alias retro-compatibili per import esistenti in altri moduli
# --------------------------------------------------------------------
# Alcuni file fanno: from backend.models import ReservationPizza
# Manteniamo l'alias per evitare ImportError senza duplicare la tabella.
ReservationPizza = Reservation

# In certi punti potrebbe apparire il plurale 'RestaurantSettings'
RestaurantSettings = RestaurantSetting

# (Aggiungiamo alias solo quando servono, per evitare conflitti)
__all__ = [
    "db",
    "Restaurant",
    "Reservation",
    "OpeningHour",
    "SpecialDay",
    "RestaurantSetting",
    "ReservationPizza",
    "RestaurantSettings",
]

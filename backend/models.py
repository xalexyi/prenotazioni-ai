# -*- coding: utf-8 -*-
# backend/models.py — Modelli DB completi + alias/sinonimi per retro-compatibilità
from __future__ import annotations

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.orm import relationship, synonym
from sqlalchemy import Numeric, UniqueConstraint

db = SQLAlchemy()

# ===========================
# Account (login)
# ===========================
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


# ===========================
# Menu: Pizza
# ===========================
class Pizza(db.Model):
    __tablename__ = "pizzas"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(Numeric(8, 2), nullable=False, default=0)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("restaurant_id", "name", name="uq_pizzas_restaurant_name"),
    )

    def __repr__(self) -> str:
        return f"<Pizza id={self.id} rid={self.restaurant_id} name={self.name!r} price={self.price}>"


# ===========================
# Prenotazioni
# ===========================
class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)

    # Canonico: customer_*
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(60))

    # Stringhe per compatibilità con il frontend ("YYYY-MM-DD" / "HH:MM")
    date = db.Column(db.String(10), nullable=False)
    time = db.Column(db.String(5), nullable=False)

    party_size = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default="confirmed")  # confirmed|pending|cancelled
    notes = db.Column(db.Text)
    source = db.Column(db.String(20))  # es. dashboard|voice|ai

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relazione con le pizze (lista di ReservationPizza)
    pizzas = relationship("ReservationPizza", back_populates="reservation", cascade="all, delete-orphan")

    # ---- Sinonimi ORM per retro-compatibilità (usabili anche nei filtri) ----
    name = synonym("customer_name")
    phone = synonym("customer_phone")
    people = synonym("party_size")

    def __repr__(self) -> str:
        return f"<Reservation id={self.id} rid={self.restaurant_id} {self.date} {self.time} name={self.customer_name!r}>"


class ReservationPizza(db.Model):
    __tablename__ = "reservation_pizzas"

    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), nullable=False, index=True)
    pizza_id = db.Column(db.Integer, db.ForeignKey("pizzas.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    reservation = relationship("Reservation", back_populates="pizzas")
    pizza = relationship("Pizza")

    __table_args__ = (
        UniqueConstraint("reservation_id", "pizza_id", name="uq_reservation_pizza_unique"),
    )

    def __repr__(self) -> str:
        return f"<ReservationPizza res={self.reservation_id} pizza={self.pizza_id} qty={self.quantity}>"


# ===========================
# Orari / Giorni speciali / Impostazioni
# ===========================
class OpeningHour(db.Model):
    __tablename__ = "opening_hours"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False)         # 0=Mon .. 6=Sun
    start_time = db.Column(db.String(5), nullable=False)    # "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)      # "HH:MM"

    __table_args__ = (db.Index("idx_opening_weekday_rest", "restaurant_id", "weekday"),)


class SpecialDay(db.Model):
    __tablename__ = "special_days"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    date = db.Column(db.String(10), nullable=False, index=True)  # "YYYY-MM-DD"
    is_closed = db.Column(db.Boolean, nullable=False, default=False)
    start_time = db.Column(db.String(5))
    end_time = db.Column(db.String(5))

    __table_args__ = (db.Index("idx_special_date_rest", "restaurant_id", "date"),)


class RestaurantSetting(db.Model):
    __tablename__ = "restaurant_settings"

    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), primary_key=True)
    tz = db.Column(db.String(64))
    slot_step_min = db.Column(db.Integer)
    last_order_min = db.Column(db.Integer)
    min_party = db.Column(db.Integer)
    max_party = db.Column(db.Integer)
    capacity_per_slot = db.Column(db.Integer)

    def __repr__(self) -> str:
        return f"<RestaurantSetting rid={self.restaurant_id} tz={self.tz!r}>"


# ===========================
# Voce / Twilio
# ===========================
class InboundNumber(db.Model):
    __tablename__ = "inbound_numbers"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    e164_number = db.Column(db.String(32), unique=True, nullable=False)  # es. +390212345678
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CallSession(db.Model):
    __tablename__ = "call_sessions"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    step = db.Column(db.String(32), nullable=False, default="start")  # start|gather|handle|done
    call_sid = db.Column(db.String(64), index=True)
    from_number = db.Column(db.String(32))
    to_number = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class CallLog(db.Model):
    __tablename__ = "call_logs"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    call_sid = db.Column(db.String(64), index=True)
    from_number = db.Column(db.String(32))
    to_number = db.Column(db.String(32))
    recording_sid = db.Column(db.String(64))
    recording_url = db.Column(db.String(512))
    duration_seconds = db.Column(db.Integer)
    transcript = db.Column(db.Text)
    received_at = db.Column(db.DateTime)                   # timestamp esterno (es. n8n)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<CallLog id={self.id} rid={self.restaurant_id} dur={self.duration_seconds}>"


# ===========================
# Export + alias retro-compatibili
# ===========================
# A volte in codice trovi il plurale:
RestaurantSettings = RestaurantSetting

__all__ = [
    "db",
    "Restaurant",
    "Reservation",
    "ReservationPizza",
    "Pizza",
    "OpeningHour",
    "SpecialDay",
    "RestaurantSetting",
    "RestaurantSettings",
    "InboundNumber",
    "CallSession",
    "CallLog",
]

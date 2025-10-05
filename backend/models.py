# -*- coding: utf-8 -*-
# backend/models.py
from __future__ import annotations

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ============================================================
#  Restaurant
# ============================================================
class Restaurant(db.Model):
    __tablename__ = "restaurants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    username = db.Column(db.String(80))
    password_hash = db.Column(db.String(255))
    slug = db.Column(db.String(80))
    logo = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relazioni
    reservations = db.relationship("Reservation", backref="restaurant", lazy=True)
    opening_hours = db.relationship("OpeningHour", backref="restaurant", lazy=True)
    special_days = db.relationship("SpecialDay", backref="restaurant", lazy=True)
    call_sessions = db.relationship("CallSession", backref="restaurant", lazy=True)

    # helpers password
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash or "", password)

    def __repr__(self):
        return f"<Restaurant {self.id} {self.name}>"

# ============================================================
#  Reservation
# ============================================================
class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    # dati cliente / prenotazione
    name = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    date = db.Column(db.String(10))    # 'YYYY-MM-DD'
    time = db.Column(db.String(5))     # 'HH:MM'
    people = db.Column(db.Integer)

    # stato / meta
    status = db.Column(db.String(20), default="pending")  # pending|confirmed|rejected
    notes = db.Column(db.Text)
    source = db.Column(db.String(20), default="voice")    # voice|manual|web
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        return {
            "id": self.id,
            "restaurant_id": self.restaurant_id,
            "name": self.name,
            "phone": self.phone,
            "date": self.date,
            "time": self.time,
            "people": self.people,
            "status": self.status,
            "notes": self.notes,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Reservation {self.id} {self.name} {self.date} {self.time}>"

# ============================================================
#  InboundNumber (Twilio / AI Voice)
# ============================================================
class InboundNumber(db.Model):
    __tablename__ = "inbound_numbers"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    number = db.Column(db.String(32), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<InboundNumber {self.number} (r{self.restaurant_id})>"

# ============================================================
#  OpeningHour (per /admin_schedule)
# ============================================================
class OpeningHour(db.Model):
    __tablename__ = "opening_hours"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    # 0 = Monday ... 6 = Sunday (coerente con datetime.weekday)
    weekday = db.Column(db.Integer, nullable=False)  # 0..6
    open_time = db.Column(db.String(5), nullable=True)   # 'HH:MM'
    close_time = db.Column(db.String(5), nullable=True)  # 'HH:MM'
    is_closed = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<OpeningHour r{self.restaurant_id} w{self.weekday} {self.open_time}-{self.close_time} closed={self.is_closed}>"

# ============================================================
#  SpecialDay (giorni speciali/festivi opzionali)
# ============================================================
class SpecialDay(db.Model):
    __tablename__ = "special_days"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    date = db.Column(db.String(10), nullable=False)      # 'YYYY-MM-DD'
    label = db.Column(db.String(120))                    # es: "Ferragosto", "Chiuso per evento"
    open_time = db.Column(db.String(5), nullable=True)   # opzionale
    close_time = db.Column(db.String(5), nullable=True)  # opzionale
    is_closed = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SpecialDay r{self.restaurant_id} {self.date} closed={self.is_closed}>"

# ============================================================
#  CallSession (log chiamate / twilio_voice)
# ============================================================
class CallSession(db.Model):
    __tablename__ = "call_sessions"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    call_sid = db.Column(db.String(64), unique=True)  # Twilio Call SID (opzionale se non usi Twilio)
    from_number = db.Column(db.String(32))
    to_number = db.Column(db.String(32))
    status = db.Column(db.String(32), default="received")  # received|in-progress|completed|failed
    duration_sec = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CallSession r{self.restaurant_id} {self.call_sid or ''}>"

# ============================================================
#  Helper init
# ============================================================
def init_db(app):
    """
    Inizializza SQLAlchemy e crea le tabelle se non esistono.
    """
    db.init_app(app)
    with app.app_context():
        db.create_all()

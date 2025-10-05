# -*- coding: utf-8 -*-
# backend/models.py
from __future__ import annotations

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ============================================================
#  Modello Restaurant
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

    # Relazioni
    reservations = db.relationship("Reservation", backref="restaurant", lazy=True)

    # Helpers password
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash or "", password)

    def __repr__(self):
        return f"<Restaurant {self.id} {self.name}>"

# ============================================================
#  Modello Reservation
# ============================================================

class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    # Dati cliente / prenotazione
    name = db.Column(db.String(120))          # alcuni progetti usano "name"
    phone = db.Column(db.String(40))
    date = db.Column(db.String(10))           # ISO 'YYYY-MM-DD'
    time = db.Column(db.String(5))            # 'HH:MM'
    people = db.Column(db.Integer)

    # Stato/metadata
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
#  Modello InboundNumber (es. Twilio / AI Voice)
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
#  Helper per inizializzazione DB
# ============================================================

def init_db(app):
    """
    Inizializza SQLAlchemy e crea le tabelle se non esistono.
    Chiama questa funzione in app.py dopo aver configurato SQLALCHEMY_DATABASE_URI.
    """
    db.init_app(app)
    with app.app_context():
        db.create_all()

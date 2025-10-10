from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash
from app import db  # istanza condivisa

# Nota: non mettere import di app.create_app qui per evitare import circolari


class Restaurant(db.Model):
    __tablename__ = "restaurant"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    logo_path = db.Column(db.String(200))
    weekly_hours_json = db.Column(db.Text)  # opzionale/legacy

    users = db.relationship("User", backref="restaurant", lazy=True)


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    # legacy "password" può esistere; usiamo password_hash
    password = db.Column(db.String(200))  # se esiste, ignorata
    password_hash = db.Column(db.String(255), nullable=True)

    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)


class Reservation(db.Model):
    __tablename__ = "reservation"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    people = db.Column(db.Integer, default=2)
    status = db.Column(db.String(40), default="Confermata")
    note = db.Column(db.Text)

    date = db.Column(db.String(10), nullable=False)  # "YYYY-MM-DD"
    time = db.Column(db.String(5), nullable=False)   # "HH:MM"


class OpeningHours(db.Model):
    __tablename__ = "opening_hours"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0..6
    windows = db.Column(db.String(200), nullable=False, default="")  # "12:00-15:00, 19:00-22:30"


class SpecialDay(db.Model):
    __tablename__ = "special_day"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    closed = db.Column(db.Boolean, default=False)
    windows = db.Column(db.String(200), default="")


class Settings(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, unique=True)

    # Prezzi & coperti
    avg_price = db.Column(db.Float, default=25.0)    # prezzo medio prenotazione
    cover = db.Column(db.Float, default=0.0)         # coperto €/persona
    seats_cap = db.Column(db.Integer)                # capacità massima (opzionale)
    min_people = db.Column(db.Integer)               # minimo prenotazioni (opzionale)

    # Menu digitale
    menu_url = db.Column(db.String(300))
    menu_desc = db.Column(db.String(300))

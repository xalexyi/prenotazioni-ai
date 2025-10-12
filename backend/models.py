from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

from app import db  # usa l'istanza db inizializzata in app.py


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    restaurant = db.relationship("Restaurant", backref=db.backref("users", lazy=True))

    def __repr__(self):
        return f"<User {self.username}>"


class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f"<Restaurant {self.name}>"


class OpeningHours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Mon ... 6=Sun
    windows = db.Column(db.String(255), nullable=False, default="")  # es: "12:00-15:00, 19:00-22:30"

    restaurant = db.relationship("Restaurant", backref=db.backref("opening_hours", lazy=True))

    __table_args__ = (db.UniqueConstraint("restaurant_id", "day_of_week", name="uix_rest_day"),)

    def __repr__(self):
        return f"<OpeningHours d={self.day_of_week} win='{self.windows}'>"


class SpecialDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    date = db.Column(db.String(10), nullable=False)  # "YYYY-MM-DD" (stringa per semplicità)
    closed = db.Column(db.Boolean, nullable=False, default=False)
    windows = db.Column(db.String(255), nullable=False, default="")

    restaurant = db.relationship("Restaurant", backref=db.backref("special_days", lazy=True))

    __table_args__ = (db.UniqueConstraint("restaurant_id", "date", name="uix_rest_date"),)

    def __repr__(self):
        return f"<SpecialDay {self.date} closed={self.closed}>"


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), unique=True, nullable=False)

    avg_price = db.Column(db.Float, nullable=True)
    cover = db.Column(db.Float, nullable=True)
    seats_cap = db.Column(db.Integer, nullable=True)
    min_people = db.Column(db.Integer, nullable=True)

    menu_url = db.Column(db.String(500), nullable=True)
    menu_desc = db.Column(db.String(500), nullable=True)

    restaurant = db.relationship("Restaurant", backref=db.backref("settings", uselist=False))

    def __repr__(self):
        return f"<Settings rest={self.restaurant_id}>"


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    name = db.Column(db.String(160), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    category = db.Column(db.String(80), nullable=True)  # esempio: "Sushi", "Pizza"
    available = db.Column(db.Boolean, nullable=False, default=True)

    restaurant = db.relationship("Restaurant", backref=db.backref("menu_items", lazy=True))

    def __repr__(self):
        return f"<MenuItem {self.name} {self.price}>"


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    date = db.Column(db.String(10), nullable=False)   # "YYYY-MM-DD"
    time = db.Column(db.String(5), nullable=False)    # "HH:MM"

    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    people = db.Column(db.Integer, nullable=False, default=2)

    status = db.Column(db.String(30), nullable=False, default="Confermata")
    note = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    restaurant = db.relationship("Restaurant", backref=db.backref("reservations", lazy=True))

    def __repr__(self):
        return f"<Reservation {self.date} {self.time} {self.name}>"

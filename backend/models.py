from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from app import db

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True)
    logo_path = db.Column(db.String)
    weekly_hours_json = db.Column(db.Text)

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    # compat: in alcuni DB c’è anche password (plain, deprecata). Usiamo password_hash.
    password = db.Column(db.String)  # legacy
    password_hash = db.Column(db.Text)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"))

class OpeningHours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"))
    weekday = db.Column(db.Integer)  # 0..6
    start_time = db.Column(db.String)  # "12:00"
    end_time = db.Column(db.String)    # "15:00"

class SpecialDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"))
    date = db.Column(db.String, unique=True)  # "YYYY-MM-DD"
    closed = db.Column(db.Boolean, default=False)
    windows = db.Column(db.String)  # "12:00-15:00, 19:00-22:30"

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"))
    avg_price = db.Column(db.Numeric)  # legacy
    seats_cap = db.Column(db.Integer)
    min_people = db.Column(db.Integer)
    # Nuovi campi
    avg_price_lunch = db.Column(db.Numeric)
    avg_price_dinner = db.Column(db.Numeric)
    cover_fee = db.Column(db.Numeric)

class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"))
    name = db.Column(db.String, nullable=False)
    price = db.Column(db.Numeric, nullable=False, default=0)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"))
    name = db.Column(db.String, nullable=False)
    phone = db.Column(db.String)
    people = db.Column(db.Integer, default=2)
    status = db.Column(db.String, default="Confermata")
    note = db.Column(db.String)
    date = db.Column(db.String)  # "YYYY-MM-DD"
    time = db.Column(db.String)  # "HH:MM"

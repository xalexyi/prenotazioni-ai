from datetime import date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash

db = SQLAlchemy()


class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    logo_path = db.Column(db.String(255))
    users = db.relationship("User", backref="restaurant", lazy=True)
    reservations = db.relationship("Reservation", backref="restaurant", lazy=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), index=True, nullable=False)
    date = db.Column(db.Date, index=True, nullable=False)
    time = db.Column(db.String(5), nullable=False)  # "20:00"
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    people = db.Column(db.Integer, default=2)
    status = db.Column(db.String(32))  # Confermata / In attesa / etc
    note = db.Column(db.Text)
    amount = db.Column(db.Numeric(10, 2), default=0)


class WeeklyHours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), index=True, nullable=False)
    weekday = db.Column(db.Integer, nullable=False)  # 0=Lun ... 6=Dom
    windows = db.Column(db.String(255), default="")  # "12:00-15:00, 19:00-23:00"


class SpecialDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), index=True, nullable=False)
    day = db.Column(db.Date, index=True, nullable=False)
    closed = db.Column(db.Boolean, default=False)
    windows = db.Column(db.String(255), default="")


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), index=True, nullable=False)
    avg_price = db.Column(db.Numeric(10, 2))
    seats_cap = db.Column(db.Integer)


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), index=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    price = db.Column(db.Numeric(10, 2), default=0)
    category = db.Column(db.String(80))
    available = db.Column(db.Boolean, default=True)

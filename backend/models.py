from datetime import datetime, time as dtime, date as ddate
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

from app import db  # usa l'istanza condivisa


class Restaurant(db.Model):
    __tablename__ = "restaurant"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    logo_path = db.Column(db.String(255), default="img/logo_robot.svg")

    users = db.relationship("User", backref="restaurant", lazy=True)
    reservations = db.relationship("Reservation", backref="restaurant", lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "logo_path": self.logo_path}


class User(UserMixin, db.Model):
    __tablename__ = "user"  # ok in Postgres
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)

    def get_id(self):
        return str(self.id)


class Reservation(db.Model):
    __tablename__ = "reservation"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    people = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/confirmed/cancelled
    notes = db.Column(db.Text, default="")
    datetime = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "people": self.people,
            "status": self.status,
            "notes": self.notes or "",
            "date": self.datetime.strftime("%d/%m/%Y"),
            "time": self.datetime.strftime("%H:%M"),
        }


class OpeningHour(db.Model):
    """
    Orari settimanali: weekday 0=lun ... 6=dom
    più righe per giorno se più finestre.
    """
    __tablename__ = "opening_hour"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)  # 0..6
    start = db.Column(db.Time, nullable=False)
    end = db.Column(db.Time, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "weekday": self.weekday,
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
        }


class SpecialDay(db.Model):
    """
    Giorni speciali/chiusure. Se closed=True, ignorare start/end.
    """
    __tablename__ = "special_day"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    day = db.Column(db.Date, nullable=False, index=True)
    closed = db.Column(db.Boolean, default=False)
    start = db.Column(db.Time)
    end = db.Column(db.Time)

    def to_dict(self):
        return {
            "id": self.id,
            "day": self.day.strftime("%d/%m/%Y"),
            "closed": bool(self.closed),
            "start": self.start.strftime("%H:%M") if self.start else None,
            "end": self.end.strftime("%H:%M") if self.end else None,
        }

# -*- coding: utf-8 -*-
# backend/models.py
from __future__ import annotations

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import check_password_hash

db = SQLAlchemy()

class Restaurant(UserMixin, db.Model):
    __tablename__ = "restaurants"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(255), nullable=False)

    email         = db.Column(db.Text)
    username      = db.Column(db.Text)
    slug          = db.Column(db.Text)
    password_hash = db.Column(db.Text)
    logo          = db.Column(db.Text)
    created_at    = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    # relations (facoltative)
    reservations  = db.relationship("Reservation", backref="restaurant", lazy="dynamic")
    inbound_numbers = db.relationship("InboundNumber", backref="restaurant", lazy="dynamic")

    def get_id(self) -> str:
        return str(self.id)

    def check_password(self, plain: str) -> bool:
        if not self.password_hash or not plain:
            return False
        try:
            return check_password_hash(self.password_hash, plain)
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<Restaurant id={self.id} name={self.name!r} username={self.username!r}>"


class Reservation(db.Model):
    __tablename__ = "reservations"

    id            = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    # campi base che la dashboard usa
    resv_date     = db.Column(db.Date, nullable=False)
    resv_time     = db.Column(db.String(8), nullable=False)  # "19:30"
    people        = db.Column(db.Integer, nullable=False, default=2)

    customer_name = db.Column(db.String(255))
    customer_phone= db.Column(db.String(32))
    notes         = db.Column(db.Text)

    created_at    = db.Column(db.DateTime(timezone=True), server_default=db.func.now())


class InboundNumber(db.Model):
    __tablename__ = "inbound_numbers"

    id            = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    phone         = db.Column(db.String(32), nullable=False)
    active        = db.Column(db.Boolean, nullable=False, default=True)

    created_at    = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

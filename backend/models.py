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

    # campi presenti in DB (mappatura ORM)
    email         = db.Column(db.Text)        # può essere NULL
    username      = db.Column(db.Text)        # può essere NULL
    slug          = db.Column(db.Text)        # può essere NULL
    password_hash = db.Column(db.Text)        # hash werkzeug
    logo          = db.Column(db.Text)        # URL/path logo
    created_at    = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    # Flask-Login
    def get_id(self) -> str:
        return str(self.id)

    # Helper login
    def check_password(self, plain: str) -> bool:
        if not self.password_hash or not plain:
            return False
        try:
            return check_password_hash(self.password_hash, plain)
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<Restaurant id={self.id} name={self.name!r} username={self.username!r}>"

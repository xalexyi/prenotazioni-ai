# -*- coding: utf-8 -*-
# backend/auth.py
from __future__ import annotations

from urllib.parse import urlparse
from typing import Optional

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, jsonify
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from backend.models import db, Restaurant

auth_bp = Blueprint("auth", __name__, url_prefix="")

# ---------- util ----------

def _is_safe_next(target: str) -> bool:
    if not target:
        return False
    u = urlparse(target)
    # consenti path relativi o stesso host senza netloc
    return (not u.netloc) and (u.scheme in ("", "http", "https"))

def _password_ok(user: Restaurant, plain: str) -> bool:
    """Gestisce sia password_hash (standard) sia eventuali campi custom."""
    if not user:
        return False
    # 1) metodo custom (se esiste)
    if hasattr(user, "check_password") and callable(getattr(user, "check_password")):
        try:
            return bool(user.check_password(plain))
        except Exception:
            pass
    # 2) campo password_hash (Werkzeug)
    if hasattr(user, "password_hash") and getattr(user, "password_hash"):
        try:
            return check_password_hash(user.password_hash, plain)
        except Exception:
            pass
    # 3) fallback ultra-basic (sconsigliato, solo per ambienti demo)
    if hasattr(user, "password") and getattr(user, "password"):
        return str(user.password) == plain
    return False

def _find_user(identifier: str) -> Optional[Restaurant]:
    """Cerca per slug/username/email/name in modo tollerante."""
    ident = (identifier or "").strip().lower()
    if not ident:
        return None

    q = Restaurant.query

    # slug
    if hasattr(Restaurant, "slug"):
        user = q.filter(Restaurant.slug == ident).first()
        if user:
            return user

    # username
    if hasattr(Restaurant, "username"):
        user = q.filter(Restaurant.username == ident).first()
        if user:
            return user

    # email
    if "@" in ident and hasattr(Restaurant, "email"):
        user = q.filter(Restaurant.email == ident).first()
        if user:
            return user

    # name (ultima spiaggia)
    if hasattr(Restaurant, "name"):
        user = q.filter(db.func.lower(Restaurant.name) == ident).first()
        if user:
            return user

    return None

def _login_and_redirect(user: Restaurant, next_url: Optional[str], remember: bool = False):
    login_user(user, remember=remember)
    session["restaurant_id"] = user.id
    if next_url and _is_safe_next(next_url):
        return redirect(next_url)
    return redirect(url_for("dashboard.index"))

# ---------- routes ----------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if getattr(current_user, "is_authenticated", False):
            nxt = request.args.get("next")
            if nxt and _is_safe_next(nxt):
                return redirect(nxt)
            return redirect(url_for("dashboard.index"))
        return render_template("login.html", error=None, next=request.args.get("next", ""))

    # POST: supporto form e JSON
    next_url = request.args.get("next") or request.form.get("next") or ""
    is_json = request.is_json
    if is_json:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        remember = bool(data.get("remember") or False)
    else:
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        remember = bool(request.form.get("remember"))

    user = _find_user(username)
    if not user or not _password_ok(user, password):
        if is_json:
            return jsonify({"ok": False, "error": "invalid_credentials"}), 401
        return render_template("login.html", error="Credenziali non valide", next=next_url), 401

    return _login_and_redirect(user, next_url, remember=remember)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("restaurant_id", None)
    return redirect(url_for("auth.login"))

# alias legacy
auth = auth_bp

# -*- coding: utf-8 -*-
# backend/auth.py
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, session, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from backend.models import db, Restaurant
from datetime import datetime

auth = Blueprint("auth", __name__, url_prefix="")

# ============================================================
#  Funzioni helper
# ============================================================

def _login_user(user: Restaurant):
    """Salva la sessione utente (ristorante)"""
    session["user_id"] = user.id
    session["restaurant_name"] = user.name
    session["restaurant_slug"] = user.slug
    session.permanent = True

def _logout_user():
    """Cancella la sessione"""
    session.clear()

def _get_current_user() -> Restaurant | None:
    """Ritorna il ristorante loggato"""
    uid = session.get("user_id")
    if not uid:
        return None
    return Restaurant.query.get(uid)

# ============================================================
#  Pagina di login
# ============================================================

@auth.route("/login", methods=["GET", "POST"])
def login():
    """Mostra form login o gestisce autenticazione"""
    if request.method == "GET":
        return render_template("login.html")

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()

    if not username or not password:
        return render_template("login.html", error="Inserisci username e password.")

    # Cerca utente per username o email
    user = Restaurant.query.filter(
        (Restaurant.username == username) | (Restaurant.email == username)
    ).first()

    if not user or not user.password_hash:
        return render_template("login.html", error="Utente non trovato o password mancante.")

    if not check_password_hash(user.password_hash, password):
        return render_template("login.html", error="Password errata.")

    _login_user(user)
    return redirect(url_for("dashboard.dashboard"))

# ============================================================
#  Logout
# ============================================================

@auth.route("/logout")
def logout():
    """Chiude la sessione e torna al login"""
    _logout_user()
    return redirect(url_for("auth.login"))

# ============================================================
#  API di registrazione (facoltativa)
# ============================================================

@auth.post("/api/register")
def api_register():
    """
    Endpoint API per creare un nuovo ristorante (solo testing/dev)
    body: {name, username, email, password}
    """
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not (name and username and password):
        return jsonify({"ok": False, "error": "Dati mancanti"}), 400

    if Restaurant.query.filter_by(username=username).first():
        return jsonify({"ok": False, "error": "Username già esistente"}), 400

    r = Restaurant(
        name=name,
        username=username,
        email=email,
        slug=username.lower().replace(" ", "-"),
        created_at=datetime.utcnow(),
    )
    r.password_hash = generate_password_hash(password)

    db.session.add(r)
    db.session.commit()
    return jsonify({"ok": True, "id": r.id})

# ============================================================
#  Rotta root → redirect automatico
# ============================================================

@auth.route("/")
def index():
    """Se loggato → dashboard, altrimenti → login"""
    if session.get("user_id"):
        return redirect(url_for("dashboard.dashboard"))
    return redirect(url_for("auth.login"))

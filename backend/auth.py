# backend/auth.py
from __future__ import annotations

from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from .models import Restaurant

auth_bp = Blueprint("auth", __name__)

# ------------------------
# util
# ------------------------
def _is_safe_next(target: str) -> bool:
    """
    Consenti redirect solo all'interno del sito (no schema/netloc esterni).
    """
    if not target:
        return False
    u = urlparse(target)
    # relative path o stesso host senza schema per sicurezza di base
    return (not u.netloc) and (u.scheme in ("", "http", "https"))

def _login_and_redirect(user: Restaurant, next_url: str | None, remember: bool = False):
    login_user(user, remember=remember)
    session["restaurant_id"] = user.id
    # redirect sicuro
    if next_url and _is_safe_next(next_url):
        return redirect(next_url)
    return redirect(url_for("dashboard.index"))

# ------------------------
# routes
# ------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        # Se già loggato, rispetta eventuale ?next=
        nxt = request.args.get("next")
        if nxt and _is_safe_next(nxt):
            return redirect(nxt)
        return redirect(url_for("dashboard.index"))

    error = None
    next_url = request.args.get("next", "")

    # Supporto login JSON
    is_json = request.is_json and request.method == "POST"
    if is_json:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        remember = bool(data.get("remember") or False)
    else:
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        remember = bool(request.form.get("remember"))

    if request.method == "POST":
        user = Restaurant.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            resp = _login_and_redirect(user, request.args.get("next"), remember=remember)
            if is_json:
                # Se la richiesta è JSON, rispondi JSON (non redirect)
                return jsonify({"ok": True, "restaurant_id": user.id}), 200
            return resp
        else:
            error = "Credenziali non valide"
            if is_json:
                return jsonify({"ok": False, "error": error}), 401

    return render_template("login.html", error=error, next=next_url)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("restaurant_id", None)
    return redirect(url_for("auth.login"))

# Alias per import legacy: from backend.auth import auth
auth = auth_bp

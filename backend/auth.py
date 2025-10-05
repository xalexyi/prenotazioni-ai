# backend/auth.py
from flask import Blueprint, request, session, redirect, url_for, jsonify
from backend.models import db, Restaurant
from werkzeug.security import check_password_hash

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # se già loggato vai in dashboard
        if session.get("restaurant_id"):
            return redirect(url_for("root.dashboard"))
        return redirect(url_for("root.login_page"))
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip().lower()
    password = (data.get("password") or "").strip()

    user = db.session.query(Restaurant).filter(db.func.lower(Restaurant.username)==username).first()
    if not user or not check_password_hash(user.password_hash or "", password):
        return jsonify({"error":"invalid_credentials"}), 401

    session["restaurant_id"] = user.id
    return jsonify({"ok": True})

@auth.route("/logout", methods=["POST", "GET"])
def logout():
    session.pop("restaurant_id", None)
    # sempre redirect alla pagina di login HTML
    return redirect(url_for("root.login_page"))

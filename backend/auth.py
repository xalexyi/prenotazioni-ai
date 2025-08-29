from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import Restaurant

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = Restaurant.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            session["restaurant_id"] = user.id
            return redirect(url_for("dashboard.index"))
        else:
            error = "Credenziali non valide"

    return render_template("login.html", error=error)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("restaurant_id", None)
    return redirect(url_for("auth.login"))

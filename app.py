import os
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from flask_cors import CORS
from werkzeug.security import check_password_hash

# -----------------------------------------------------------------------------
# DB
# -----------------------------------------------------------------------------
db = SQLAlchemy()


def _normalize_db_url(url: str) -> str:
    # Render/Heroku a volte danno "postgres://", SQLAlchemy vuole "postgresql://"
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


# -----------------------------------------------------------------------------
# App factory
# -----------------------------------------------------------------------------
def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    # Config
    database_url = _normalize_db_url(os.getenv("DATABASE_URL", ""))
    if not database_url:
        os.makedirs("instance", exist_ok=True)
        database_url = "sqlite:///instance/dev.sqlite3"

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_SORT_KEYS=False,
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret"),
        REMEMBER_COOKIE_DURATION=60 * 60 * 24 * 30,  # 30 giorni
    )

    # Init estensioni
    db.init_app(app)

    # Modelli (compatibile con root o backend/)
    try:
        from models import User, Restaurant  # type: ignore
    except Exception:  # pragma: no cover
        from backend.models import User, Restaurant  # type: ignore

    # Login manager
    login_manager = LoginManager(app)
    login_manager.login_view = "login"  # se non loggato → /login

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            # Evita di tenere sessioni rotte in caso di tabelle non create
            return None

    # Context comuni ai template
    @app.context_processor
    def inject_globals():
        rest_name = None
        try:
            rest = Restaurant.query.first()
            if rest:
                rest_name = rest.name
        except Exception:
            pass
        return dict(now=datetime.utcnow(), rest_name=rest_name)

    # -----------------------------------------------------------------------------
    # ROUTES
    # -----------------------------------------------------------------------------

    # Home = login
    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """
        GET: mostra login
        POST: autentica e reindirizza al dashboard
        """
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            remember = bool(request.form.get("remember"))

            user = None
            try:
                # username case-sensitive (come avevi prima)
                user = User.query.filter_by(username=username).first()
            except Exception:
                user = None

            if not user:
                flash("Utente inesistente.", "error")
                return render_template("login.html"), 401

            # password: accetta sia hash che plain (per ambienti test)
            ok = False
            try:
                ok = check_password_hash(user.password, password)
            except Exception:
                ok = (user.password == password)

            if not ok:
                flash("Password errata.", "error")
                return render_template("login.html"), 401

            login_user(user, remember=remember)
            return redirect(url_for("dashboard"))

        # GET
        return render_template("login.html")

    @app.route("/logout", methods=["POST", "GET"])
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        # Mostra la tua dashboard (template già presente nel progetto)
        return render_template("dashboard.html")

    @app.get("/healthz")
    def healthz():
        return jsonify(ok=True, service="prenotazioni-ai")

    # -----------------------------------------------------------------------------
    # Blueprints opzionali (registrati SOLO se presenti)
    # -----------------------------------------------------------------------------
    # voice_slots → /api/voice/slot/*
    try:
        try:
            from backend.voice_slots import bp_voice_slots  # type: ignore
        except Exception:
            from voice_slots import bp_voice_slots  # type: ignore
        app.register_blueprint(bp_voice_slots, url_prefix="/api/voice/slot")
    except Exception:
        # se non esiste nessuno dei due, ignora senza rompere il boot
        pass

    return app


# Istanza WSGI per gunicorn
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

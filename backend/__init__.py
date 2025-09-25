# backend/__init__.py
import os
from pathlib import Path
from flask import Flask
from flask_login import LoginManager

from backend.models import db, Restaurant


def _maybe_create_instance_dir(db_uri: str) -> None:
    """
    Se stiamo usando SQLite in instance/, assicuriamoci che la cartella esista.
    """
    if db_uri.startswith("sqlite:///instance/"):
        Path("instance").mkdir(parents=True, exist_ok=True)


def create_app():
    app = Flask(
        __name__,
        static_folder="../static",
        template_folder="../templates",
    )

    # ===== Secret =====
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    # ===== Database (Render/Heroku compatibile) =====
    db_url = os.environ.get("DATABASE_URL", "sqlite:///instance/database.db")
    if db_url.startswith("postgres://"):
        # compat vecchi URI Heroku
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    _maybe_create_instance_dir(db_url)

    # ===== SQLAlchemy =====
    db.init_app(app)

    # ===== Login =====
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return Restaurant.query.get(int(user_id))
        except Exception:
            return None

    # ===== Config aggiuntive utili =====
    # Badge voce: numero massimo linee (fallback 3)
    app.config.setdefault("VOICE_MAX", int(os.environ.get("VOICE_MAX_ACTIVE", "3")))
    # Versione build per eventuale cache-busting client
    app.config["BUILD_VERSION"] = os.environ.get("BUILD_VERSION", "dev")

    # ===== Blueprint =====
    from backend.root import bp as root_bp
    from backend.auth import auth_bp
    from backend.dashboard import bp as dashboard_bp
    from backend.api import api as api_bp
    from backend.voice_slots import voice_bp          # /api/public/voice/*
    from backend.admin_schedule import api_admin       # /api/admin/* (token)
    from backend.twilio_voice import twilio_bp         # /twilio/*

    app.register_blueprint(root_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(api_admin)
    app.register_blueprint(twilio_bp)

    # ===== Context processor (facoltativo ma utile) =====
    @app.context_processor
    def inject_build_version():
        return {"BUILD_VERSION": app.config.get("BUILD_VERSION", "dev")}

    return app


# Entry-point WSGI (gunicorn usa "app:app")
app = create_app()

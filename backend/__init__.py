# -*- coding: utf-8 -*-
# backend/__init__.py

import os
from pathlib import Path
from typing import Optional, Dict, Any

from flask import Flask
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.models import db, Restaurant

# -----------------------------
# Helpers
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # cartella progetto


def _maybe_create_instance_dir(db_uri: str) -> None:
    """Se usiamo SQLite in instance/, assicuriamoci che la cartella esista."""
    if db_uri.startswith("sqlite:///instance/"):
        (BASE_DIR / "instance").mkdir(parents=True, exist_ok=True)


def _normalize_db_url(raw: str) -> str:
    """
    Normalizza DATABASE_URL per compatibilità Heroku/Render:
    - postgres://  -> postgresql://
    - aggiunge sslmode=require se Postgres e manca
    """
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql://", 1)
    if raw.startswith("postgresql://") and "sslmode=" not in raw:
        sep = "&" if "?" in raw else "?"
        raw = f"{raw}{sep}sslmode=require"
    return raw


# -----------------------------
# App factory
# -----------------------------
def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    app = Flask(
        __name__,
        static_folder=str((BASE_DIR / "static").resolve()),
        template_folder=str((BASE_DIR / "templates").resolve()),
    )

    # On Render siamo dietro proxy: abilita uso corretto di X-Forwarded-*
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # ===== Secret =====
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    # ===== Database =====
    db_url = os.environ.get("DATABASE_URL", "sqlite:///instance/database.db")
    db_url = _normalize_db_url(db_url)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,  # evita connessioni zombie (es. Render)
    }
    _maybe_create_instance_dir(db_url)

    # ===== Config extra utili =====
    app.config.setdefault("VOICE_MAX", int(os.environ.get("VOICE_MAX_ACTIVE", "3")))
    app.config["BUILD_VERSION"] = os.environ.get("BUILD_VERSION", "dev")
    app.config.setdefault("JSON_SORT_KEYS", False)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    # In produzione su HTTPS, consigliare:
    if os.environ.get("FLASK_ENV") == "production":
        app.config.setdefault("SESSION_COOKIE_SECURE", True)

    if test_config:
        app.config.update(test_config)

    # ===== Estensioni =====
    db.init_app(app)

    # ===== Login (il "tenant" è Restaurant) =====
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return Restaurant.query.get(int(user_id))
        except Exception:
            return None

    # ===== Blueprint =====
    from backend.root import bp as root_bp
    from backend.auth import auth_bp
    from backend.dashboard import bp as dashboard_bp
    from backend.api import api as api_bp
    from backend.voice_slots import voice_bp                  # /api/public/voice/*
    from backend.admin_schedule import api_admin              # /api/admin-token/* (token)
    from backend.twilio_voice import twilio_bp                # /twilio/*
    from backend.public_sessions import public_sessions_bp    # /api/public/sessions/*

    app.register_blueprint(root_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(api_admin)
    app.register_blueprint(twilio_bp)
    app.register_blueprint(public_sessions_bp)

    # ===== Context processor =====
    @app.context_processor
    def inject_build_version():
        return {"BUILD_VERSION": app.config.get("BUILD_VERSION", "dev")}

    return app


# Entry-point WSGI (es. gunicorn "backend:app")
app = create_app()

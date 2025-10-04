# -*- coding: utf-8 -*-
# backend/__init__.py

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from flask import Flask, jsonify
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
import logging

from backend.models import db, Restaurant  # non modifico i tuoi modelli

BASE_DIR = Path(__file__).resolve().parent.parent


def _normalize_db_url(raw: str) -> str:
    """Render dà spesso 'postgres://'. SQLAlchemy vuole 'postgresql://'.
    Inoltre forziamo sslmode=require in produzione.
    """
    if not raw:
        return raw
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql://", 1)
    if raw.startswith("postgresql://") and "sslmode=" not in raw:
        raw += ("&" if "?" in raw else "?") + "sslmode=require"
    return raw


def _setup_logging(app: Flask) -> None:
    """Tutto su stdout (Render). Logga anche gli stacktrace."""
    gunicorn_error = logging.getLogger("gunicorn.error")
    if gunicorn_error.handlers:
        app.logger.handlers = gunicorn_error.handlers
        app.logger.setLevel(gunicorn_error.level or logging.INFO)
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    app = Flask(
        __name__,
        static_folder=str((BASE_DIR / "static").resolve()),
        template_folder=str((BASE_DIR / "templates").resolve()),
    )

    # -------- Config base --------
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_db_url(
        os.environ.get("DATABASE_URL", os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///instance/app.db"))
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
    app.config["BUILD_VERSION"] = os.environ.get("BUILD_VERSION", "dev")

    if test_config:
        app.config.update(test_config)

    _setup_logging(app)

    # -------- DB + Login --------
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return Restaurant.query.get(int(user_id))
        except Exception:
            return None

    # -------- Blueprints --------
    from backend.root import bp as root_bp
    from backend.auth import auth_bp
    from backend.dashboard import bp as dashboard_bp

    # Questi sono opzionali: se esistono li registro, altrimenti continuo
    def _safe_register(import_path: str, attr: str):
        try:
            mod = __import__(import_path, fromlist=[attr])
            app.register_blueprint(getattr(mod, attr))
            app.logger.info("Registered blueprint: %s.%s", import_path, attr)
        except Exception as e:
            app.logger.warning("Blueprint %s non registrato (%s)", import_path, e)

    app.register_blueprint(root_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    _safe_register("backend.api", "api")
    _safe_register("backend.admin_schedule", "bp")
    _safe_register("backend.twilio_voice", "bp")
    _safe_register("backend.public_sessions", "public_sessions_bp")

    # -------- Health + error logging --------
    @app.get("/health")
    def health():
        return {
            "ok": True,
            "build_version": app.config.get("BUILD_VERSION", "dev"),
        }

    @app.errorhandler(Exception)
    def _unhandled(e):
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "internal_error"}), 500

    @app.context_processor
    def inject_build_version():
        return {"BUILD_VERSION": app.config.get("BUILD_VERSION", "dev")}

    return app


# WSGI entrypoint
app = create_app()

# backend/__init__.py
import os
from flask import Flask
from flask_login import LoginManager

from backend.models import db, Restaurant


def create_app():
    app = Flask(
        __name__,
        static_folder="../static",
        template_folder="../templates",
    )

    # Secret
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    # Database (Render/Heroku compatibile)
    db_url = os.environ.get("DATABASE_URL", "sqlite:///instance/database.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # SQLAlchemy
    db.init_app(app)

    # Login
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Restaurant.query.get(int(user_id))

    # ===== BLUEPRINTS =====
    from backend.root import bp as root_bp
    from backend.auth import auth_bp
    from backend.dashboard import bp as dashboard_bp
    from backend.api import api as api_bp
    from backend.voice_slots import voice_bp          # /api/public/voice/*
    from backend.admin_schedule import api_admin       # /api/admin/* (token)

    app.register_blueprint(root_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(api_admin)

    # cache-busting per gli asset statici
    app.config["BUILD_VERSION"] = os.environ.get("BUILD_VERSION", "dev")

    return app


# WSGI entrypoint (gunicorn usa "app:app")
app = create_app()

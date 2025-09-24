# backend/__init__.py
import os
from flask import Flask
from flask_login import LoginManager

from backend.models import db, Restaurant

def create_app():
    # cartelle statiche/template: sono a livello progetto
    app = Flask(__name__, static_folder="../static", template_folder="../templates")

    # chiave app
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    # database (compatibilità render/heroku: postgres:// -> postgresql://)
    db_url = os.environ.get("DATABASE_URL", "sqlite:///instance/database.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # init ORM
    db.init_app(app)

    # login
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Restaurant.query.get(int(user_id))

    # ====== BLUEPRINTS ======
    # base/site/api esistenti
    from backend.root import bp as root_bp
    from backend.api import api as api_bp
    from backend.auth import auth_bp
    from backend.dashboard import bp as dashboard_bp
    from backend.twilio_voice import twilio_bp

    # voice slots (contatore chiamate attive)
    from backend.voice_slots import voice_bp

    # ORARI SU DB: lettura pubblica + admin “comandi” (nuovi)
    from backend.api_schedule import api_schedule
    from backend.admin_schedule import api_admin

    # registra
    app.register_blueprint(root_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(twilio_bp)      # /twilio/...
    app.register_blueprint(voice_bp)       # /api/public/voice/...
    app.register_blueprint(api_schedule)   # /api/public/opening-hours
    app.register_blueprint(api_admin)      # /api/admin/*  (richiede X-Admin-Token)

    return app

# compat con gunicorn: `gunicorn app:app`
app = create_app()

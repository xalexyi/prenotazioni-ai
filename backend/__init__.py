# backend/__init__.py
import os
from flask import Flask
from flask_login import LoginManager

from backend.models import db, Restaurant
from backend.api_schedule import api_schedule
app.register_blueprint(api_schedule)


def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="../templates")

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    db_url = os.environ.get("DATABASE_URL", "sqlite:///instance/database.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Restaurant.query.get(int(user_id))

    # === BLUEPRINTS ESISTENTI ===
    from backend.root import bp as root_bp
    from backend.api import api as api_bp
    from backend.auth import auth_bp
    from backend.dashboard import bp as dashboard_bp
    from backend.twilio_voice import twilio_bp
    from backend.voice_slots import voice_bp            # contatore chiamate
    from backend.admin_schedule import api_admin        # comandi orari (ce l'hai)

    app.register_blueprint(root_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(twilio_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(api_admin)

    return app

app = create_app()

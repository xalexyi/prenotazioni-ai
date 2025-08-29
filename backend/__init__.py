import os
from flask import Flask
from dotenv import load_dotenv
from flask_login import LoginManager
from .models import db, Restaurant

login_manager = LoginManager()
login_manager.login_view = "auth.login"

@login_manager.user_loader
def load_user(user_id):
    try:
        return Restaurant.query.get(int(user_id))
    except Exception:
        return None

def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

    db_uri = (
        os.getenv("SQLALCHEMY_DATABASE_URI")
        or os.getenv("DATABASE_URL")
        or "sqlite:///instance/app.db"
    )
    if db_uri.startswith("sqlite:///instance/"):
        os.makedirs("instance", exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    # Blueprints core
    from .auth import auth_bp
    from .api import api as api_bp
    from .dashboard import bp as dashboard_bp
    from .root import root_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(root_bp)

    # Twilio (lazy import, così non blocca i comandi se manca la libreria)
    try:
        from .twilio_voice import twilio_bp
        app.register_blueprint(twilio_bp)
    except Exception as e:
        # Log silenzioso in dev; se vuoi, metti app.logger.warning(...)
        pass

    return app

# backend/__init__.py
import os
from flask import Flask
from backend.models import db

def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="../templates")

    # Secret key per sessioni
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    # DB URL: usa DATABASE_URL se presente, altrimenti sqlite locale
    db_url = os.environ.get("DATABASE_URL", "sqlite:///instance/database.db")
    # Fix per Render/Heroku che usano 'postgres://' invece di 'postgresql://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Crea automaticamente le tabelle se non esistono
    with app.app_context():
        db.create_all()

    # importa e registra le blueprint
    from backend.root import bp as root_bp
    from backend.api import api as api_bp
    from backend.auth import auth as auth_bp
    from backend.dashboard import dash as dash_bp

    app.register_blueprint(root_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)

    return app

# compatibile con gunicorn (Start Command: gunicorn app:app)
app = create_app()

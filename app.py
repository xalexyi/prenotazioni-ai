import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

# -----------------------------------------------------------------------------
# DB setup (unico punto d'ingresso)
# -----------------------------------------------------------------------------
db = SQLAlchemy()


def _normalize_db_url(url: str) -> str:
    """
    Render/Heroku a volte forniscono 'postgres://...' ma SQLAlchemy vuole 'postgresql://...'
    """
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    # ------------------- Config -------------------
    database_url = _normalize_db_url(os.getenv("DATABASE_URL", ""))
    if not database_url:
        database_url = "sqlite:///instance/dev.sqlite3"
        os.makedirs("instance", exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_SORT_KEYS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    # Inizializza DB
    db.init_app(app)

    # ------------------- Modelli -------------------
    # I tuoi modelli stanno in backend/models.py
    try:
        from backend.models import User, Restaurant  # type: ignore
    except Exception:
        # fallback se i modelli fossero in models.py (root)
        from models import User, Restaurant  # type: ignore

    # ------------------- Login Manager -------------------
    login_manager = LoginManager()
    login_manager.login_view = "login_page"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            # SQLAlchemy 2.x
            return db.session.get(User, int(user_id))  # type: ignore[attr-defined]
        except Exception:
            # compat vecchia API
            return User.query.get(int(user_id))  # type: ignore[attr-defined]

    # ------------------- Rotte di autenticazione -------------------
    @app.route("/", methods=["GET"])
    def login_page():
        # Mostra login sempre come prima pagina
        return render_template("login.html")

    @app.route("/login", methods=["POST"])
    def login():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()  # type: ignore[attr-defined]
        if not user or not check_password_hash(user.password, password):
            flash("Credenziali non valide", "error")
            return redirect(url_for("login_page"))

        login_user(user)
        return redirect(url_for("dashboard"))

    @app.route("/logout", methods=["POST", "GET"])
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    # ------------------- Dashboard protetta -------------------
    @app.route("/dashboard", methods=["GET"])
    @login_required
    def dashboard():
        # Qui puoi caricare dati del ristorante associato all'utente
        rest = None
        if current_user and getattr(current_user, "restaurant_id", None):
            rest = db.session.get(Restaurant, current_user.restaurant_id)  # type: ignore
        return render_template("dashboard.html", restaurant=rest)

    # ------------------- Blueprint: voice_slots -------------------
    # /api/voice/slot/acquire  e  /api/voice/slot/release
    from backend.voice_slots import bp_voice_slots  # <-- IMPORT PULITO (usa SQL grezzo, no modelli)
    app.register_blueprint(bp_voice_slots)

    # ------------------- Healthcheck -------------------
    @app.get("/healthz")
    def _health():
        return {"ok": True}

    return app


# Per gunicorn: `web: gunicorn app:app`
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

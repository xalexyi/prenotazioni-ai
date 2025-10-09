import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import (
    LoginManager, login_user, login_required, logout_user, current_user
)
from werkzeug.security import check_password_hash

# -------------------------------
# DB e Login setup (singletons)
# -------------------------------
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login_page"  # dove rimandare se non autenticato


def _normalize_db_url(url: str) -> str:
    # Render/Heroku: 'postgres://' -> 'postgresql://'
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    # ------------------- Config -------------------
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

    # ------------------- Init estensioni -------------------
    db.init_app(app)
    login_manager.init_app(app)

    # ------------------- Import modelli -------------------
    # Accetta sia layout root (models.py) che backend/models.py
    try:
        import models  # type: ignore
    except Exception:
        from backend import models  # type: ignore

    User = models.User  # type: ignore

    # ------------------- user_loader robusto -------------------
    @login_manager.user_loader
    def load_user(user_id: str):
        """
        FIX: se la tabella non esiste / transazione abortita / id inesistente,
        fai rollback e torna None, così /login non esplode mai.
        """
        try:
            # SQLAlchemy 2.x: preferisci session.get, ma gestiamo entrambi
            try:
                return db.session.get(User, int(user_id))  # type: ignore
            except Exception:
                return User.query.get(int(user_id))  # type: ignore
        except Exception:
            db.session.rollback()
            return None

    # ------------------- Blueprint opzionali -------------------
    # (non facciamo fallire l'app se mancano)
    for dotted in ["backend.voice_slots:bp_voice_slots", "voice_slots:bp_voice_slots"]:
        try:
            mod_name, var_name = dotted.split(":")
            mod = __import__(mod_name, fromlist=[var_name])
            app.register_blueprint(getattr(mod, var_name))
            break
        except Exception:
            pass

    # ------------------- Routes -------------------
    @app.get("/")
    def root():
        # Se loggato vai in dashboard, altrimenti login
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login_page"))

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        # Se arriva con sessione sporca che causava i 500, user_loader ora torna None
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            remember = request.form.get("remember") is not None

            try:
                user = User.query.filter_by(username=username).first()  # type: ignore
            except Exception as e:
                db.session.rollback()
                flash("Errore database durante il login.")
                return render_template("login.html"), 500

            if not user:
                flash("Credenziali non valide.")
                return render_template("login.html"), 401

            ok = False
            try:
                ok = check_password_hash(user.password, password)  # type: ignore
            except Exception:
                # nel caso password sia già in chiaro (dev)
                ok = (user.password == password)  # type: ignore

            if not ok:
                flash("Credenziali non valide.")
                return render_template("login.html"), 401

            login_user(user, remember=remember)
            return redirect(url_for("dashboard"))

        # GET
        return render_template("login.html")

    @app.get("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "service": "prenotazioni-ai"}

    # ------------------- Error handlers (hardening) -------------------
    @app.errorhandler(500)
    def _e500(e):
        try:
            db.session.rollback()
        except Exception:
            pass
        # Mostra pagina d'errore generica senza rompere
        return render_template("login.html"), 500

    return app


# Per gunicorn su Render
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

db = SQLAlchemy()
login_manager = LoginManager()


def _normalize_db_url(url: str) -> str:
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
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")  # per sessioni/login

    # Init estensioni
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login_page"  # dove reindirizzare se non loggato
    login_manager.login_message_category = "info"

    # ------------------- Import modelli -------------------
    # Cerco User in models o backend.models
    User = None
    try:
        import models  # type: ignore
        User = getattr(models, "User", None)
    except Exception:
        try:
            from backend import models as _models  # type: ignore
            User = getattr(_models, "User", None)
        except Exception:
            pass

    if User is None:
        # senza User non posso autenticare
        @login_manager.user_loader
        def _no_user_loader(_user_id: str):
            return None
    else:
        @login_manager.user_loader
        def load_user(user_id: str):
            try:
                # SQLAlchemy 2.x
                return db.session.get(User, int(user_id))
            except Exception:
                return User.query.get(int(user_id))  # type: ignore[attr-defined]

    # ------------------- Blueprints esistenti (se presenti) -------------
    for dotted in [
        "backend.api_public:bp_public",
        "backend.auth:bp_auth",         # se hai già le route di auth, restano valide
        "backend.admin:bp_admin",
        "backend.dashboard:bp_dashboard",
    ]:
        try:
            module_name, var_name = dotted.split(":")
            mod = __import__(module_name, fromlist=[var_name])
            app.register_blueprint(getattr(mod, var_name))
        except Exception:
            pass

    # ------------------- Voice slots endpoints --------------------------
    try:
        from backend.voice_slots import bp_voice_slots
    except Exception:
        from voice_slots import bp_voice_slots  # type: ignore
    app.register_blueprint(bp_voice_slots)

    # ------------------- Healthcheck -----------------------------------
    @app.get("/healthz")
    def _health():
        return {"ok": True}

    # ------------------- Auth minimale ---------------------------------
    # HOME = pagina di login
    @app.get("/")
    def login_page():
        return render_template("login.html")

    # POST /login supporta form HTML (email/password) o JSON
    @app.post("/login")
    def login_post():
        if User is None:
            abort(500, description="User model non disponibile: non posso autenticare.")

        if request.is_json:
            payload = request.get_json(silent=True) or {}
            email = (payload.get("email") or "").strip().lower()
            password = payload.get("password") or ""
        else:
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""

        if not email or not password:
            return render_template("login.html", error="Inserisci email e password"), 400

        # Trova utente
        try:
            # Preferisci User.query.filter_by(...)
            user = User.query.filter_by(email=email).first()  # type: ignore[attr-defined]
        except Exception:
            # SQLAlchemy 2.x con session
            stmt = db.select(User).filter_by(email=email)
            user = db.session.execute(stmt).scalar_one_or_none()

        if not user:
            return render_template("login.html", error="Credenziali non valide"), 401

        # Verifica password: prova metodo custom, altrimenti check hash
        ok = False
        if hasattr(user, "check_password"):
            try:
                ok = bool(user.check_password(password))  # type: ignore[attr-defined]
            except Exception:
                ok = False
        if not ok:
            # fallback su password_hash
            pwd_hash = getattr(user, "password_hash", None)
            if pwd_hash:
                ok = check_password_hash(pwd_hash, password)

        if not ok:
            return render_template("login.html", error="Credenziali non valide"), 401

        login_user(user)  # crea la sessione
        # redirect alla dashboard
        return redirect(url_for("dashboard_page"))

    @app.get("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    # ------------------- UI: dashboard PROTETTA ------------------------
    @app.get("/dashboard")
    @login_required
    def dashboard_page():
        # qui sei sicuro che current_user è autenticato
        # puoi passare info al template se ti serve
        return render_template("dashboard.html", user=current_user)

    # Endpoint di info rapido
    @app.get("/__info")
    def __info():
        return jsonify(
            ok=True,
            auth=bool(current_user.is_authenticated),
            user=getattr(current_user, "email", None),
            routes=["/", "/login", "/logout", "/dashboard (protetta)", "/healthz"],
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

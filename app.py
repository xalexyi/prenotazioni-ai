import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

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
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    # Init estensioni
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login_page"
    login_manager.login_message_category = "info"

    # ------------------- Import modelli -------------------
    # I tuoi modelli stanno in models.py (o backend/models.py)
    User = Restaurant = None
    try:
        import models  # type: ignore
        User = getattr(models, "User", None)
        Restaurant = getattr(models, "Restaurant", None)
    except Exception:
        try:
            from backend import models as _models  # type: ignore
            User = getattr(_models, "User", None)
            Restaurant = getattr(_models, "Restaurant", None)
        except Exception:
            pass

    if User is None:
        @login_manager.user_loader
        def _no_user_loader(_user_id: str):
            return None
    else:
        @login_manager.user_loader
        def load_user(user_id: str):
            try:
                return db.session.get(User, int(user_id))
            except Exception:
                return User.query.get(int(user_id))  # type: ignore[attr-defined]

    # ------------------- Blueprints esistenti (se presenti) -------------
    for dotted in [
        "backend.api_public:bp_public",
        "backend.auth:bp_auth",
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

    # ------------------- Auth (UI) -------------------------------------
    @app.get("/")
    def login_page():
        return render_template("login.html")

    @app.post("/login", endpoint="login")
    def login_post():
        if User is None:
            abort(500, description="User model non disponibile.")

        # i tuoi template usano 'username' / 'password'
        if request.is_json:
            payload = request.get_json(silent=True) or {}
            username = (payload.get("username") or "").strip()
            password = payload.get("password") or ""
        else:
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

        if not username or not password:
            return render_template("login.html", error="Inserisci username e password"), 400

        # cerca user
        try:
            user = User.query.filter_by(username=username).first()  # type: ignore[attr-defined]
        except Exception:
            stmt = db.select(User).filter_by(username=username)
            user = db.session.execute(stmt).scalar_one_or_none()

        if not user:
            return render_template("login.html", error="Credenziali non valide"), 401

        stored = getattr(user, "password", None)
        ok = False
        if isinstance(stored, str) and (
            stored.startswith("pbkdf2:") or stored.startswith("scrypt:") or stored.startswith("argon2:")
        ):
            ok = check_password_hash(stored, password)
        else:
            ok = (stored == password)

        if not ok:
            return render_template("login.html", error="Credenziali non valide"), 401

        login_user(user)
        return redirect(url_for("dashboard_page"))

    @app.get("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    @app.get("/dashboard")
    @login_required
    def dashboard_page():
        return render_template("dashboard.html", user=current_user)

    # ------------------- BOOTSTRAP TEMPORANEO (crea tabelle + admin) ----
    BOOT_TOKEN = os.getenv("ADMIN_BOOTSTRAP_TOKEN", "")

    def _check_bootstrap_token():
        if not BOOT_TOKEN:
            abort(403, description="ADMIN_BOOTSTRAP_TOKEN non impostato.")
        hdr = request.headers.get("X-Bootstrap-Token", "")
        if hdr != BOOT_TOKEN:
            abort(403, description="X-Bootstrap-Token errato.")

    @app.post("/admin/bootstrap/init")
    def bootstrap_init():
        """Crea tutte le tabelle dei modelli."""
        _check_bootstrap_token()
        if User is None:
            abort(500, description="Modelli non importati.")

        with app.app_context():
            db.create_all()
        return jsonify(ok=True, created=True)

    @app.post("/admin/bootstrap/seed-admin")
    def bootstrap_seed_admin():
        """
        Crea (se mancano) un Restaurant di default e un utente admin.
        Env usate:
          ADMIN_USERNAME (default: admin)
          ADMIN_PASSWORD (default: changeme)
          ADMIN_RESTAURANT (default: 'Haru Asian Fusion Restaurant')
        """
        _check_bootstrap_token()
        if User is None or Restaurant is None:
            abort(500, description="Modelli non importati.")

        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "changeme")
        admin_hash = generate_password_hash(admin_password)

        rest_name = os.getenv("ADMIN_RESTAURANT", "Haru Asian Fusion Restaurant")

        # crea restaurant se manca
        rest = Restaurant.query.filter_by(name=rest_name).first()
        if not rest:
            rest = Restaurant(name=rest_name, logo_path="img/logo_robot.svg")
            db.session.add(rest)
            db.session.commit()

        # crea user se manca
        user = User.query.filter_by(username=admin_username).first()
        if not user:
            user = User(username=admin_username, password=admin_hash, restaurant_id=rest.id)
            db.session.add(user)
            db.session.commit()
            created = True
        else:
            # aggiorna password se vuoi forzare
            user.password = admin_hash
            db.session.commit()
            created = False

        return jsonify(ok=True, restaurant_id=rest.id, user_id=user.id, created=created)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

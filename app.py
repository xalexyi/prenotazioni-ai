# app.py
import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()


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

    db.init_app(app)

    # ------------------- Import modelli (best-effort) -------------------
    try:
        import models  # noqa: F401
    except Exception:
        try:
            from backend import models as _models  # noqa: F401
        except Exception:
            pass

    # ------------------- Blueprints esistenti (se presenti) -------------
    for dotted in [
        "backend.api_public:bp_public",
        "backend.auth:bp_auth",         # ← se hai le route di login/logout qui, restano valide
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

    # ------------------- UI: login come home, dashboard separata --------
    @app.get("/")
    def login_page():
        # pagina iniziale = login
        return render_template("login.html")

    @app.get("/dashboard")
    def dashboard_page():
        # pagina dashboard (se vuoi proteggerla con Flask-Login,
        # aggiungi @login_required qui oppure gestiscilo nel blueprint auth)
        return render_template("dashboard.html")

    # ------------------- Healthcheck -----------------------------------
    @app.get("/healthz")
    def _health():
        return {"ok": True}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

# app.py
import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# -----------------------------------------------------------------------------
# DB setup (unico punto d'ingresso)
# -----------------------------------------------------------------------------
db = SQLAlchemy()


def _normalize_db_url(url: str) -> str:
    """Render/Heroku: 'postgres://' -> 'postgresql://' per SQLAlchemy."""
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    # ------------------- Config -------------------
    database_url = _normalize_db_url(os.getenv("DATABASE_URL", ""))
    if not database_url:
        # fallback locale (solo dev)
        database_url = "sqlite:///instance/dev.sqlite3"
        os.makedirs("instance", exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_SORT_KEYS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    # Inizializza DB
    db.init_app(app)

    # ------------------- Import modelli -------------------
    # Carichiamo i modelli così le tabelle sono note all'app
    try:
        import models  # noqa: F401
    except Exception:
        try:
            from backend import models as _models  # noqa: F401
        except Exception:
            pass

    # ------------------- Blueprint di base esistenti (se presenti) -------------------
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

    # ------------------- (NUOVO) Blueprint: voice_slots -------------------
    # /api/voice/slot/acquire  e  /api/voice/slot/release
    try:
        from backend.voice_slots import bp_voice_slots
    except Exception:
        from voice_slots import bp_voice_slots  # type: ignore
    app.register_blueprint(bp_voice_slots)

    # ------------------- Healthcheck & root -------------------
    @app.get("/healthz")
    def _health():
        return {"ok": True}

    @app.get("/")
    def _root():
        # Facoltativo: pagina base per evitare 404 in homepage
        return jsonify(ok=True, service="prenotazioni-ai", docs="/healthz")

    return app


# Per gunicorn: `web: gunicorn app:app`
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

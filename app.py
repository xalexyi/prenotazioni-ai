# app.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# -----------------------------------------------------------------------------
# DB setup (unico punto d'ingresso, non rompe import esistenti)
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
    # Prende DATABASE_URL dall'ambiente Render
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

    # ------------------- Import modelli (non tocco la tua struttura) -------------------
    # Carica i modelli così le tabelle esistono quando serve
    try:
        import models  # noqa: F401
    except Exception:
        try:
            from backend import models as _models  # noqa: F401
        except Exception:
            pass  # se i modelli vengono importati altrove, va comunque bene

    # ------------------- Blueprint di base esistenti (se presenti) -------------------
    # Registriamo eventuali blueprint già nel tuo progetto, ma solo se esistono.
    # Questi try/except NON alterano la tua struttura: se non ci sono, saltano.
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
        # Se hai messo voice_slots.py accanto a app.py
        from voice_slots import bp_voice_slots  # type: ignore
    app.register_blueprint(bp_voice_slots)

    # ------------------- (OPZIONALE) Blueprint admin_sql una-tantum -------------------
    # Attivalo SOLO se vuoi inizializzare il DB via /admin/sql/init-active-calls,
    # poi rimuovi questa registrazione per sicurezza.
    try:
        from backend.admin_sql import bp_admin_sql  # type: ignore
        app.register_blueprint(bp_admin_sql)
    except Exception:
        pass

    # ------------------- Healthcheck semplice -------------------
    @app.get("/healthz")
    def _health():
        return {"ok": True}

    return app


# Per gunicorn: `web: gunicorn app:app` (Render)
app = create_app()

if __name__ == "__main__":
    # Avvio locale
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

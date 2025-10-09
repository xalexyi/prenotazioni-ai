# app.py
import os
from flask import Flask, render_template, jsonify, Response
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

    # ------------------- UI Routes (con fallback) -----------------------
    FALLBACK_HTML = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prenotazioni AI</title>
<link rel="stylesheet" href="/static/css/styles.css">
</head>
<body style="font-family:system-ui,Segoe UI,Roboto,Arial;padding:24px;max-width:900px;margin:auto">
  <h1>🟢 Prenotazioni AI</h1>
  <p>Backend attivo. La pagina dashboard non è disponibile o ha richiesto variabili non fornite.</p>
  <ul>
    <li><a href="/healthz">/healthz</a> – stato</li>
    <li><a href="/dashboard">/dashboard</a> – prova a caricare il template</li>
  </ul>
</body>
</html>"""

    def _safe_render(name: str) -> Response:
        """
        Prova a renderizzare un template. Se manca o il template va in errore
        (es. variabili attese non presenti), torna una landing HTML di fallback.
        """
        try:
            return render_template(name)
        except Exception as e:
            # Logga l’errore su console (visibile nei Logs di Render)
            print(f"[ui] render_template('{name}') FAILED: {e}")
            return Response(FALLBACK_HTML, mimetype="text/html")

    @app.get("/")
    def home():
        # prova dashboard.html -> fallback HTML statico
        return _safe_render("dashboard.html")

    @app.get("/dashboard")
    def dashboard():
        return _safe_render("dashboard.html")

    @app.get("/login")
    def login_page():
        return _safe_render("login.html")

    # endpoint di servizio
    @app.get("/__info")
    def __info():
        return jsonify(ok=True, service="prenotazioni-ai", routes=["/", "/dashboard", "/login", "/healthz"])

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

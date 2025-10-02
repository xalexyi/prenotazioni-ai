# -*- coding: utf-8 -*-
# backend/__init__.py — factory Flask, DB, login, blueprint, context

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from flask import Flask, jsonify, request, g
from flask_login import LoginManager, current_user, login_required

from .models import db, Restaurant, Reservation, OpeningHour, SpecialDay, RestaurantSetting

# =========================================================
# Config di base
# =========================================================
def _config_app(app: Flask) -> None:
    app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret"))
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", os.environ.get("DATABASE_URL", "sqlite:///app.db"))
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("JSON_SORT_KEYS", False)
    # Build/version per cache-busting statici
    app.config.setdefault("BUILD_VERSION", os.environ.get("BUILD_VERSION", datetime.utcnow().strftime("%Y%m%d%H%M%S")))


# =========================================================
# Login manager
# =========================================================
login_manager = LoginManager()
login_manager.login_view = "auth.login"  # se in futuro aggiungi blueprint auth


@login_manager.user_loader
def load_user(user_id: str) -> Optional[Restaurant]:
    if not user_id:
        return None
    try:
        return Restaurant.query.get(int(user_id))
    except Exception:
        return None


# =========================================================
# Context helpers
# =========================================================
def _active_restaurant() -> Restaurant:
    """
    Prova a determinare il ristorante 'attivo' per il rendering template:
    - se utente loggato: usa current_user
    - altrimenti ?restaurant_id= o header X-Restaurant-Id
    - fallback: primo ristorante in DB o un placeholder
    """
    if getattr(current_user, "is_authenticated", False):
        return current_user  # type: ignore[return-value]

    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        hdr = request.headers.get("X-Restaurant-Id")
        if hdr and hdr.isdigit():
            rid = int(hdr)

    if rid:
        r = Restaurant.query.get(rid)
        if r:
            return r

    r = Restaurant.query.first()
    if r:
        return r

    # placeholder (non persistito): evita crash nei template
    dummy = Restaurant(id=0, name="Ristorante")
    return dummy


# =========================================================
# Factory
# =========================================================
def create_app() -> Flask:
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    _config_app(app)

    # Init estensioni
    db.init_app(app)
    login_manager.init_app(app)

    # Creazione tabelle in dev se mancano (safe)
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            # In produzione potresti usare Alembic/migrazioni
            pass

    # ------------------ Blueprint amministrativo (API) ------------------
    # Import qui per evitare cicli
    from .admin_schedule import api_admin as api_admin_token
    app.register_blueprint(api_admin_token)

    # ------------------ Blueprint pubblico minimal ---------------------
    from flask import Blueprint

    api_public = Blueprint("api_public", __name__, url_prefix="/api/public")

    @api_public.get("/sessions/<sid>")
    def get_public_session(sid: str):
        """
        Endpoint usato dal frontend per recuperare l'admin token.
        Ritorna anche (se disponibile) un restaurant_id dedotto.
        """
        admin_token = os.environ.get("ADMIN_TOKEN", "").strip()
        rid = None
        if getattr(current_user, "is_authenticated", False):
            rid = int(current_user.id)  # type: ignore[attr-defined]
        else:
            qrid = request.args.get("restaurant_id", type=int)
            if qrid:
                rid = qrid
            else:
                # fallback: primo ristorante se esiste (non sensibile)
                first = Restaurant.query.first()
                rid = int(first.id) if first else 1

        return jsonify({
            "ok": True,
            "session_id": sid,
            "admin_token": admin_token,
            "restaurant_id": rid,
        })

    @api_public.get("/health")
    def health_public():
        return jsonify({"ok": True, "time": datetime.utcnow().isoformat() + "Z"})

    app.register_blueprint(api_public)

    # Alias /health root-level (utile per Render uptime checks)
    @app.get("/health")
    def health_root():
        return jsonify({"ok": True, "time": datetime.utcnow().isoformat() + "Z"})

    # ------------------ Context processor (variabili template) ----------
    @app.context_processor
    def inject_globals():
        r = _active_restaurant()
        today = datetime.now().date().isoformat()
        # Se nel template servono altre costanti, aggiungile qui
        return {
            "restaurant": r,
            "today": today,
            "config": app.config,  # per BUILD_VERSION
        }

    # ------------------ Error handlers puliti ---------------------------
    @app.errorhandler(400)
    def _bad_request(e):
        # Se la richiesta è JSON aspettati risposta JSON
        if request.accept_mimetypes.best == "application/json" or request.is_json:
            return jsonify({"ok": False, "error": "bad_request", "detail": getattr(e, "description", str(e))}), 400
        return (getattr(e, "description", "Bad request"), 400)

    @app.errorhandler(401)
    def _unauth(e):
        if request.accept_mimetypes.best == "application/json" or request.is_json:
            return jsonify({"ok": False, "error": "unauthorized", "detail": getattr(e, "description", str(e))}), 401
        return ("Unauthorized", 401)

    @app.errorhandler(404)
    def _not_found(e):
        if request.accept_mimetypes.best == "application/json" or request.is_json:
            return jsonify({"ok": False, "error": "not_found"}), 404
        return ("Not found", 404)

    @app.errorhandler(500)
    def _server_error(e):
        if request.accept_mimetypes.best == "application/json" or request.is_json:
            return jsonify({"ok": False, "error": "server_error"}), 500
        return ("Server error", 500)

    return app

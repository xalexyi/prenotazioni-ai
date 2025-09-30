# -*- coding: utf-8 -*-
# backend/public_sessions.py

from flask import Blueprint, request, jsonify, session, current_app
import secrets
import os

public_sessions_bp = Blueprint("public_sessions", __name__, url_prefix="/api/public/sessions")

# ================================================
# Utility
# ================================================

def _sid_from_path(sid: str) -> str:
    """Ritorna l'ID di sessione richiesto (sanitizzato)."""
    sid = (sid or "").strip()
    if not sid or len(sid) > 64:
        raise ValueError("Session ID non valido")
    return sid

def _get_admin_token() -> str:
    """Restituisce l'admin token dal config/env."""
    return os.environ.get("ADMIN_TOKEN") or current_app.config.get("ADMIN_TOKEN")

# ================================================
# Routes
# ================================================

@public_sessions_bp.get("/<sid>")
def get_session(sid):
    """
    Restituisce la sessione pubblica.
    Se non esiste, la crea al volo.
    Ritorna sempre admin_token (necessario al frontend).
    """
    try:
        sid = _sid_from_path(sid)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid session id"}), 400

    token = _get_admin_token()
    if not token:
        return jsonify({"ok": False, "error": "ADMIN_TOKEN non configurato"}), 500

    # In futuro potresti persistere info utente/tenant se serve.
    data = {
        "sid": sid,
        "admin_token": token,
    }
    return jsonify(data)


@public_sessions_bp.patch("/<sid>")
def patch_session(sid):
    """
    Permette di aggiornare valori nella sessione (ad es. memorizzare admin_token locale).
    Non usato molto, ma utile per debug/manuale.
    """
    try:
        sid = _sid_from_path(sid)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid session id"}), 400

    payload = request.get_json(silent=True) or {}
    # al momento gestiamo solo admin_token
    token = payload.get("admin_token")
    if token:
        session["admin_token"] = token

    return jsonify({"ok": True, "sid": sid, "session": dict(session)})


@public_sessions_bp.get("/@me")
def session_me():
    """
    Restituisce la sessione corrente del browser (cookie-based).
    Utile se non vuoi gestire sid manualmente.
    """
    token = session.get("admin_token") or _get_admin_token()
    if not token:
        return jsonify({"ok": False, "error": "Nessun admin_token"}), 404
    return jsonify({"sid": session.get("sid") or "anon", "admin_token": token})

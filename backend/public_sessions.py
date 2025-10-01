# -*- coding: utf-8 -*-
# backend/public_sessions.py

from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, current_app, jsonify, request

public_sessions_bp = Blueprint("public_sessions", __name__, url_prefix="/api/public/sessions")

def _store() -> Dict[str, Any]:
    return current_app.config.setdefault("_sessions", {})

@public_sessions_bp.get("/<sid>")
def get_session(sid: str):
    return jsonify(_store().get(sid, {}))

@public_sessions_bp.patch("/<sid>")
def patch_session(sid: str):
    data = request.get_json(force=True, silent=True) or {}
    store = _store()

    update = data.get("update")
    if update is None and "session" in data:
        update = {"session": data.get("session")}
    if update is None:
        update = {}

    # compat: consenti sia root fields che session: {...}
    root_updates = {}
    sess_updates = {}
    if "session" in update and isinstance(update["session"], dict):
        sess_updates = update["session"]
    else:
        # se passano direttamente { admin_token: "..." }
        root_updates = update

    current = store.get(sid, {})
    merged = {**current, **root_updates}
    if sess_updates:
        merged["session"] = {**current.get("session", {}), **sess_updates}

    store[sid] = merged
    return jsonify({"ok": True, "session": store[sid]})

@public_sessions_bp.post("/<sid>")
def post_session(sid: str):
    return patch_session(sid)

@public_sessions_bp.delete("/<sid>")
def delete_session(sid: str):
    store = _store()
    if sid in store:
        del store[sid]
        return jsonify({"ok": True, "deleted": sid})
    return jsonify({"ok": False, "error": "not_found"}), 404

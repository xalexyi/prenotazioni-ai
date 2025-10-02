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
    data = request.get_json(silent=True) or {}
    store = _store()
    cur = store.get(sid, {})
    merged = {**cur, **data}
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

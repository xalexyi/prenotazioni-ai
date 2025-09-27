# -*- coding: utf-8 -*-
# backend/root.py
from __future__ import annotations

from datetime import datetime
from flask import Blueprint, redirect, url_for, jsonify, request, current_app

# Il blueprint deve chiamarsi "bp" perché __init__.py lo importa così.
bp = Blueprint("root", __name__)

@bp.route("/")
def root_index():
    """Reindirizza alla pagina di login (blueprint 'auth')."""
    return redirect(url_for("auth.login"))


@bp.route("/health", methods=["GET", "HEAD"])
def health():
    """
    Endpoint di healthcheck per Render / orchestratori.
    Risponde sia a GET che a HEAD. Include build_version se presente.
    """
    if request.method == "HEAD":
        return ("", 200)

    build = current_app.config.get("BUILD_VERSION", "dev")
    return jsonify({
        "ok": True,
        "status": "ok",
        "build_version": build,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }), 200

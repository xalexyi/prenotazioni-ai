# backend/root.py
from __future__ import annotations

from datetime import datetime
from flask import Blueprint, redirect, url_for, jsonify, request

# Il blueprint deve chiamarsi "bp" perché __init__.py lo importa così.
bp = Blueprint("root", __name__)

@bp.route("/")
def root_index():
    """
    Reindirizza alla pagina di login (blueprint 'auth').
    """
    return redirect(url_for("auth.login"))

@bp.route("/health", methods=["GET", "HEAD"])
def health():
    """
    Endpoint di healthcheck per Render / orchestratori.
    Risponde sia a GET che a HEAD.
    """
    if request.method == "HEAD":
        return ("", 200)
    return jsonify({
        "ok": True,
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })

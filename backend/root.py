# -*- coding: utf-8 -*-
# backend/root.py
from __future__ import annotations

from datetime import datetime
from flask import Blueprint, redirect, url_for, jsonify, request, current_app

bp = Blueprint("root", __name__)

@bp.route("/")
def root_index():
    return redirect(url_for("auth.login"))

@bp.route("/health", methods=["GET", "HEAD"])
def health():
    if request.method == "HEAD":
        return ("", 200)
    build = current_app.config.get("BUILD_VERSION", "dev")
    return jsonify({
        "ok": True,
        "status": "ok",
        "build_version": build,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }), 200

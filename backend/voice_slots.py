# -*- coding: utf-8 -*-
# backend/voice_slots.py
"""
Endpoint pubblici legati alla 'voce' (stato linea/chiamate attive).
- URL prefix: /api/public/voice
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, current_app

from backend.models import db, CallSession

voice_bp = Blueprint("voice", __name__, url_prefix="/api/public/voice")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


@voice_bp.get("/active/<int:rid>")
def voice_active(rid: int):
    """
    Ritorna quante chiamate sono 'attive' per il ristorante:
      - active   = CallSession con step != 'done' negli ultimi N minuti
      - max      = soglia massima (VOICE_MAX_ACTIVE / config VOICE_MAX, default 3)
      - overload = active >= max
    """
    lookback_min = _env_int("VOICE_LOOKBACK_MIN", 5)
    max_active = (
        _env_int("VOICE_MAX_ACTIVE", current_app.config.get("VOICE_MAX", 3))
    )

    since = datetime.utcnow() - timedelta(minutes=lookback_min)

    active = (
        db.session.query(CallSession)
        .filter(
            CallSession.restaurant_id == rid,
            CallSession.created_at >= since,
            CallSession.step != "done",
        )
        .count()
    )

    return jsonify(
        {
            "active": int(active),
            "max": int(max_active),
            "overload": bool(active >= max_active),
        }
    )

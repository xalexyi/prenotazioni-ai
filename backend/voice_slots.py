# backend/voice_slots.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from threading import Lock

voice_bp = Blueprint("voice_public", __name__)

# Registro in-memory: { restaurant_id: { CallSid: datetime_utc } }
_ACTIVE = {}
_LOCK = Lock()

MAX_CALLS_PER_RESTAURANT = 3
TTL_SECONDS = 5 * 60  # sicurezza: se non arriva lo status, scade dopo 5 minuti


def _purge_expired(rid: int):
    """Rimuove dal registro le chiamate scadute per un dato ristorante."""
    now = datetime.utcnow()
    calls = _ACTIVE.get(rid, {})
    expired = [cs for cs, ts in calls.items() if (now - ts).total_seconds() > TTL_SECONDS]
    for cs in expired:
        calls.pop(cs, None)
    if not calls:
        _ACTIVE.pop(rid, None)


@voice_bp.post("/api/public/voice/acquire")
def voice_acquire():
    """
    Body JSON:
    {
      "restaurant_id": 1,
      "call_sid": "CAxxx"
    }
    Ritorna: { "ok": true, "overload": bool, "active": int }
    """
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    csid = (data.get("call_sid") or "").strip()

    if not (rid and csid):
        return jsonify({"ok": False, "error": "missing restaurant_id or call_sid"}), 400

    with _LOCK:
        _purge_expired(rid)
        calls = _ACTIVE.setdefault(rid, {})
        # idempotente: se già registrata, ritorna stato attuale
        if csid in calls:
            return jsonify({"ok": True, "overload": False, "active": len(calls)}), 200

        if len(calls) >= MAX_CALLS_PER_RESTAURANT:
            return jsonify({"ok": True, "overload": True, "active": len(calls)}), 200

        calls[csid] = datetime.utcnow()
        return jsonify({"ok": True, "overload": False, "active": len(calls)}), 200


@voice_bp.post("/api/public/voice/release")
def voice_release():
    """
    Body JSON:
    {
      "restaurant_id": 1,
      "call_sid": "CAxxx"
    }
    Ritorna: { "ok": true }
    """
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    csid = (data.get("call_sid") or "").strip()

    with _LOCK:
        if rid in _ACTIVE and csid in _ACTIVE[rid]:
            _ACTIVE[rid].pop(csid, None)
            if not _ACTIVE[rid]:
                _ACTIVE.pop(rid, None)

    return jsonify({"ok": True}), 200


@voice_bp.get("/api/public/voice/health")
def voice_health():
    """Solo per debug/monitor."""
    with _LOCK:
        active = {rid: len(calls) for rid, calls in _ACTIVE.items()}
    return jsonify({"ok": True, "active": active, "max": MAX_CALLS_PER_RESTAURANT}), 200


@voice_bp.get("/api/public/voice/active/<int:rid>")
def voice_active_by_param(rid: int):
    """
    GET /api/public/voice/active/1  -> { "ok": true, "active": 0, "max": 3 }
    """
    with _LOCK:
        _purge_expired(rid)
        n = len(_ACTIVE.get(rid, {}))
    return jsonify({"ok": True, "active": n, "max": MAX_CALLS_PER_RESTAURANT}), 200


@voice_bp.get("/api/public/voice/active")
def voice_active_by_query():
    """
    GET /api/public/voice/active?restaurant_id=1
    """
    try:
        rid = int(request.args.get("restaurant_id") or 0)
    except Exception:
        rid = 0
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400
    with _LOCK:
        _purge_expired(rid)
        n = len(_ACTIVE.get(rid, {}))
    return jsonify({"ok": True, "active": n, "max": MAX_CALLS_PER_RESTAURANT}), 200

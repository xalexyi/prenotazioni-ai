# backend/voice_slots.py
from flask import Blueprint, request, jsonify
from sqlalchemy import func

# import robusti per db e modello
try:
    from backend import db  # se hai un backend package che re-exporta db
except Exception:
    try:
        from app import db
    except Exception:
        from . import db  # se sei in un package

try:
    from models import ActiveCall   # models.py in root
except Exception:
    from backend.models import ActiveCall  # se i modelli sono in backend/models.py

bp_voice_slots = Blueprint("voice_slots", __name__, url_prefix="/api/voice/slot")


def _get_json():
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict()
    return data


@bp_voice_slots.route("/acquire", methods=["POST"])
def acquire_slot():
    """
    Body: { restaurant_id:int, call_sid:str, max:int? }
    Ritorno: { overload:bool, active_count:int }
    """
    p = _get_json()
    try:
        rid = int(p.get("restaurant_id") or 0)
    except Exception:
        rid = 0
    call_sid = (p.get("call_sid") or "").strip()
    max_concurrent = int(p.get("max") or 3)

    if not rid or not call_sid:
        return jsonify(error=True, reason="MISSING_FIELDS"), 400

    # ripulisci eventuali pendenti troppo vecchie
    ActiveCall.cleanup(ttl_minutes=10)

    active_count = (db.session.query(func.count(ActiveCall.id))
                    .filter_by(restaurant_id=rid, active=True)
                    .scalar())

    if active_count >= max_concurrent:
        return jsonify(overload=True, active_count=active_count), 200

    # upsert idempotente su call_sid
    rec = ActiveCall.query.filter_by(call_sid=call_sid).one_or_none()
    if rec:
        rec.active = True
        rec.restaurant_id = rid
    else:
        rec = ActiveCall(restaurant_id=rid, call_sid=call_sid, active=True)
        db.session.add(rec)

    db.session.commit()

    active_count = (db.session.query(func.count(ActiveCall.id))
                    .filter_by(restaurant_id=rid, active=True)
                    .scalar())

    return jsonify(overload=False, active_count=active_count), 200


@bp_voice_slots.route("/release", methods=["POST"])
def release_slot():
    """
    Body: { call_sid:str }
    Ritorno: { released:bool }
    """
    p = _get_json()
    call_sid = (p.get("call_sid") or "").strip()
    if not call_sid:
        return jsonify(error=True, reason="MISSING_CALLSID"), 400

    rec = ActiveCall.query.filter_by(call_sid=call_sid).one_or_none()
    if rec and rec.active:
        rec.active = False
        db.session.commit()
        return jsonify(released=True), 200

    return jsonify(released=False), 200

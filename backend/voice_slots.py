# backend/voice_slots.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from backend.models import db
from sqlalchemy import and_

voice_bp = Blueprint("voice_bp", __name__, url_prefix="/api/public/voice")

# Config (max linee contemporanee)
MAX_ACTIVE = 3

# Tabellina minimale in DB per tracciare le chiamate attive
from sqlalchemy import Column, Integer, String, DateTime

from backend.models import Base  # se non hai Base, togli e usa db.Model

class VoiceSlot(db.Model):  # se usi declarative_base, adegua
    __tablename__ = "voice_slots"
    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, nullable=False, index=True)
    call_sid = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

# acquire: prova ad occupare uno slot
@voice_bp.post("/acquire")
def acquire():
    data = request.get_json(force=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    csid = (data.get("call_sid") or "").strip()
    if not rid or not csid:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    # elimina vecchi slot zombie > 4 ore
    cutoff = datetime.utcnow() - timedelta(hours=4)
    db.session.query(VoiceSlot).filter(VoiceSlot.created_at < cutoff).delete()

    active = db.session.query(VoiceSlot).filter_by(restaurant_id=rid).count()
    overload = active >= MAX_ACTIVE

    # Se già presente, non duplicare
    exists = db.session.query(VoiceSlot).filter_by(call_sid=csid).first()
    if not exists and not overload:
        db.session.add(VoiceSlot(restaurant_id=rid, call_sid=csid))
        db.session.commit()
        active += 1

    return jsonify({"ok": True, "active": active, "overload": active >= MAX_ACTIVE})

# release: libera lo slot
@voice_bp.post("/release")
def release():
    data = request.get_json(force=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    csid = (data.get("call_sid") or "").strip()
    if not rid or not csid:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    db.session.query(VoiceSlot).filter_by(restaurant_id=rid, call_sid=csid).delete()
    db.session.commit()
    return jsonify({"ok": True})

# active: stato corrente
@voice_bp.get("/active/<int:rid>")
def active(rid: int):
    active = db.session.query(VoiceSlot).filter_by(restaurant_id=rid).count()
    return jsonify({"ok": True, "active": active, "max": MAX_ACTIVE})

from flask import Blueprint, request, jsonify
from sqlalchemy import text
from app import db

bp_voice_slots = Blueprint("voice_slots", __name__, url_prefix="/api/voice/slot")


def _bool(v):
    # Converte valori Postgres in boolean Python in modo sicuro
    if isinstance(v, bool):
        return v
    if v in (1, "1", "t", "true", "True", "TRUE"):
        return True
    return False


@bp_voice_slots.post("/acquire")
def acquire_slot():
    """
    Body JSON:
    {
      "restaurant_id": 1,
      "call_sid": "CA_xxx",
      "max": 3
    }

    Ritorna:
    { "restaurant_id": 1, "call_sid": "CA_xxx", "overload": false }
    """
    data = request.get_json(force=True, silent=True) or {}

    rid = int(data.get("restaurant_id") or 0)
    csid = (data.get("call_sid") or "").strip()
    max_calls = int(data.get("max") or 3)

    if not rid or not csid:
        return jsonify(error="restaurant_id e call_sid sono obbligatori"), 400

    try:
        # Chiama la funzione SQL (creata via 2025-10-active-calls.sql)
        # acquire_slot(rid, call_sid, max) -> boolean (TRUE se overload)
        res = db.session.execute(
            text("SELECT acquire_slot(:rid, :csid, :max) AS overload"),
            {"rid": rid, "csid": csid, "max": max_calls},
        ).mappings().first()

        overload = _bool(res["overload"]) if res is not None else True
        db.session.commit()

        return jsonify(
            restaurant_id=rid,
            call_sid=csid,
            overload=overload,
            version="pg-func-1",
        )
    except Exception as e:
        db.session.rollback()
        # Fallback di emergenza (se le funzioni non esistono)
        # Controllo conteggio attivi e poi inserimento grezzo
        try:
            cnt = db.session.execute(
                text(
                    "SELECT COUNT(*) AS n FROM active_calls WHERE restaurant_id=:rid AND active=TRUE"
                ),
                {"rid": rid},
            ).scalar()
            if cnt is None:
                cnt = 0

            if int(cnt) >= max_calls:
                return jsonify(
                    restaurant_id=rid, call_sid=csid, overload=True, version="fallback-raw"
                ), 200

            db.session.execute(
                text(
                    """
                    INSERT INTO active_calls (restaurant_id, call_sid, active)
                    VALUES (:rid, :csid, TRUE)
                    ON CONFLICT (call_sid) DO UPDATE
                      SET active = EXCLUDED.active,
                          restaurant_id = EXCLUDED.restaurant_id
                    """
                ),
                {"rid": rid, "csid": csid},
            )
            db.session.commit()
            return jsonify(
                restaurant_id=rid, call_sid=csid, overload=False, version="fallback-raw"
            ), 200
        except Exception as e2:
            db.session.rollback()
            return jsonify(error=f"acquire failed: {e2}"), 500


@bp_voice_slots.post("/release")
def release_slot():
    """
    Body JSON:
    {
      "call_sid": "CA_xxx"
    }

    Ritorna:
    { "released": true }
    """
    data = request.get_json(force=True, silent=True) or {}
    csid = (data.get("call_sid") or "").strip()

    if not csid:
        return jsonify(error="call_sid è obbligatorio"), 400

    try:
        # Chiama la funzione SQL (creata via 2025-10-active-calls.sql)
        res = db.session.execute(
            text("SELECT release_slot(:csid) AS released"),
            {"csid": csid},
        ).mappings().first()

        released = _bool(res["released"]) if res is not None else False
        db.session.commit()
        return jsonify(released=released, version="pg-func-1")
    except Exception as e:
        db.session.rollback()
        # Fallback: update diretto
        try:
            res = db.session.execute(
                text(
                    "UPDATE active_calls SET active=FALSE WHERE call_sid=:csid AND active=TRUE RETURNING TRUE AS released"
                ),
                {"csid": csid},
            ).mappings().first()
            db.session.commit()
            return jsonify(released=bool(res["released"]) if res else False, version="fallback-raw")
        except Exception as e2:
            db.session.rollback()
            return jsonify(error=f"release failed: {e2}"), 500

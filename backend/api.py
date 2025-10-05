# backend/api.py
from flask import Blueprint, request, jsonify, session
from backend.models import db, Restaurant
from datetime import datetime

api = Blueprint("api", __name__, url_prefix="/api")

def _require_restaurant():
    rid = session.get("restaurant_id")
    if not rid:
        return None
    return db.session.get(Restaurant, rid)

@api.route("/admin/state")
def admin_state():
    r = _require_restaurant()
    if not r: return jsonify({"error":"unauthorized"}), 401
    return jsonify({
        "weekly_hours": r.weekly_hours or {},
        "settings": r.settings or {},
        "special_days": r.special_days or []
    })

@api.route("/admin/weekly_hours", methods=["POST"])
def save_weekly_hours():
    r = _require_restaurant()
    if not r: return jsonify({"error":"unauthorized"}), 401
    data = request.get_json(force=True)
    r.weekly_hours = data
    db.session.commit()
    return jsonify({"ok": True})

@api.route("/admin/special_day", methods=["POST", "DELETE"])
def special_day():
    r = _require_restaurant()
    if not r: return jsonify({"error":"unauthorized"}), 401
    data = request.get_json(force=True)
    date = data.get("date")
    if not date: return jsonify({"error":"missing_date"}), 400
    items = list(r.special_days or [])
    if request.method == "DELETE":
        items = [x for x in items if x.get("date") != date]
    else:
        # upsert
        found = False
        for x in items:
            if x.get("date") == date:
                x.update({"closed": bool(data.get("closed")), "windows": data.get("windows")})
                found = True
                break
        if not found:
            items.append({"date": date, "closed": bool(data.get("closed")), "windows": data.get("windows")})
    r.special_days = items
    db.session.commit()
    return jsonify({"ok": True})

@api.route("/admin/settings", methods=["POST"])
def save_settings():
    r = _require_restaurant()
    if not r: return jsonify({"error":"unauthorized"}), 401
    s = request.get_json(force=True)
    r.settings = s
    db.session.commit()
    return jsonify({"ok": True})

@api.route("/admin/token", methods=["POST"])
def save_token():
    r = _require_restaurant()
    if not r: return jsonify({"error":"unauthorized"}), 401
    tok = (request.get_json(force=True) or {}).get("token","")
    r.api_token = tok
    db.session.commit()
    return jsonify({"ok": True})

@api.route("/admin/booking", methods=["POST"])
def create_booking():
    r = _require_restaurant()
    if not r: return jsonify({"error":"unauthorized"}), 401
    # qui salva la prenotazione nel tuo modello “Reservation”
    # Placeholder: solo dimostrazione
    return jsonify({"ok": True})

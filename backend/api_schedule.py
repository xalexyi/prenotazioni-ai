# backend/api_schedule.py
from flask import Blueprint, request, jsonify
from backend.rules_service import OpeningHour, SpecialDay, rules_from_db

api_schedule = Blueprint("api_schedule", __name__)

@api_schedule.get("/api/public/opening-hours")
def get_opening_hours():
    rid = int(request.args.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    rules = rules_from_db(rid)
    weekly = {
        wd: [f"{s.start.strftime('%H:%M')}-{s.end.strftime('%H:%M')}" for s in slots]
        for wd, slots in rules.weekly.items()
    }
    specials = SpecialDay.query.filter_by(restaurant_id=rid).order_by(SpecialDay.date).all()
    sd = []
    for r in specials:
        sd.append({
            "date": r.date,
            "is_closed": bool(r.is_closed),
            "start_time": r.start_time,
            "end_time": r.end_time,
        })

    return jsonify({
        "ok": True,
        "weekly": weekly,
        "special_days": sd,
        "meta": {
            "slot_step_min": rules.slot_step_min,
            "last_order_min": rules.last_order_min,
            "min_party": rules.min_party,
            "max_party": rules.max_party,
            "capacity_per_slot": rules.capacity_per_slot,
        },
    }), 200

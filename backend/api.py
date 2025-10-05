# -*- coding: utf-8 -*-
# backend/api.py
from __future__ import annotations

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session

from backend.models import db, Reservation
from backend.ai import summarize_day, analyze_hours, greeting_based_on_time

api = Blueprint("api", __name__, url_prefix="/api")


# ----------------------------------------------------------
#  Helper per autenticazione semplice
# ----------------------------------------------------------
def _require_login() -> bool:
    return bool(session.get("user_id"))


# ----------------------------------------------------------
#  Lista prenotazioni (con filtro di intervallo)
#    GET /api/reservations?range=today|last30|all
# ----------------------------------------------------------
@api.get("/reservations")
def get_reservations():
    if not _require_login():
        return jsonify([])

    rng = (request.args.get("range") or "today").lower().strip()
    q = Reservation.query

    if rng == "today":
        today_iso = datetime.utcnow().date().isoformat()
        q = q.filter(Reservation.date == today_iso)
    elif rng == "last30":
        start = (datetime.utcnow().date() - timedelta(days=30)).isoformat()
        q = q.filter(Reservation.date >= start)
    # "all" => nessun filtro aggiuntivo

    q = q.order_by(Reservation.date.desc(), Reservation.time.asc())
    res = q.all()

    return jsonify([
        {
            "id": r.id,
            "name": getattr(r, "name", None) or getattr(r, "customer_name", None),
            "phone": getattr(r, "phone", None),
            "date": getattr(r, "date", None),
            "time": getattr(r, "time", None),
            "people": getattr(r, "people", None),
            "status": getattr(r, "status", None),
            "notes": getattr(r, "notes", None),
        }
        for r in res
    ])


# ----------------------------------------------------------
#  Riepilogo AI (generato lato backend)
#    POST /api/ai/summary
#    body: { total, people, confirmed }
# ----------------------------------------------------------
@api.post("/ai/summary")
def ai_summary():
    if not _require_login():
        return jsonify({"summary": "Non autenticato."})

    data = request.get_json(silent=True) or {}
    total = int(data.get("total") or 0)
    people = int(data.get("people") or 0)
    confirmed = int(data.get("confirmed") or 0)

    text = summarize_day(total, people, confirmed)
    greet = greeting_based_on_time()

    return jsonify({"summary": f"{greet}! {text}"})


# ----------------------------------------------------------
#  Analisi automatica orari (euristiche)
#    GET /api/admin/hours/insights
# ----------------------------------------------------------
@api.get("/admin/hours/insights")
def hours_insights():
    if not _require_login():
        return jsonify({"insights": ["Non autenticato."]})

    insights = analyze_hours()
    return jsonify({"insights": insights})


# ----------------------------------------------------------
#  Healthcheck semplice
#    GET /api/health
# ----------------------------------------------------------
@api.get("/health")
def health():
    return jsonify({
        "ok": True,
        "user": bool(session.get("user_id")),
        "time": datetime.utcnow().isoformat(timespec="seconds"),
    })

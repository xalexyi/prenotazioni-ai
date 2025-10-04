# -*- coding: utf-8 -*-
# backend/api.py
from __future__ import annotations

from datetime import date
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import and_

from backend.models import db, Reservation

api = Blueprint("api", __name__, url_prefix="/api")

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None

@api.get("/reservations")
@login_required
def list_reservations():
    """Lista prenotazioni filtrabili per data. Default: oggi."""
    d = _parse_date(request.args.get("date")) or date.today()
    q = Reservation.query.filter(
        and_(Reservation.restaurant_id == current_user.id, Reservation.resv_date == d)
    ).order_by(Reservation.resv_time.asc())
    items = [{
        "id": r.id,
        "date": r.resv_date.isoformat(),
        "time": r.resv_time,
        "people": r.people,
        "name": r.customer_name,
        "phone": r.customer_phone,
        "notes": r.notes or "",
    } for r in q.all()]
    return jsonify({"ok": True, "items": items})

@api.post("/reservations")
@login_required
def create_reservation():
    """Crea una prenotazione dalla form 'Nuova prenotazione'."""
    data = request.get_json(silent=True) or request.form

    d = _parse_date(data.get("date"))
    t = (data.get("time") or "").strip()
    people = int(data.get("people") or 2)
    name   = (data.get("name") or "").strip()
    phone  = (data.get("phone") or "").strip()
    notes  = (data.get("notes") or "").strip()

    if not d or not t or people < 1:
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    r = Reservation(
        restaurant_id=current_user.id,
        resv_date=d, resv_time=t, people=people,
        customer_name=name, customer_phone=phone, notes=notes
    )
    db.session.add(r)
    db.session.commit()

    return jsonify({"ok": True, "id": r.id})

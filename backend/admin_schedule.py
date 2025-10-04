# -*- coding: utf-8 -*-
# backend/admin_schedule.py — API gestionali (prenotazioni, orari, speciali, impostazioni)
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from flask import Blueprint, request, jsonify, abort, render_template
from flask_login import current_user
from sqlalchemy import or_

# IMPORTA I MODELLI SOLO DA backend.models (niente duplicazioni)
from backend.models import (
    db,
    Reservation,
    OpeningHour,
    SpecialDay,
    RestaurantSetting,
)

api_admin = Blueprint("api_admin", __name__)
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()

_RX_HHMM = re.compile(r"^\d{1,2}:\d{2}$")
_RX_ISOD = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ---------- Auth ----------
def _auth() -> None:
    tok = request.headers.get("X-Admin-Token") or request.args.get("token")
    if tok and ADMIN_TOKEN and tok == ADMIN_TOKEN:
        return
    rid_arg = request.args.get("restaurant_id", type=int)
    rid_body = None
    if request.is_json:
        rid_body = (request.get_json(silent=True) or {}).get("restaurant_id")
    rid = rid_arg or rid_body
    if getattr(current_user, "is_authenticated", False):
        if not rid or int(rid) == int(getattr(current_user, "id", 0)):
            return
    abort(401, description="unauthorized")

# ---------- Utils ----------
def _hhmm(s: str) -> str:
    s = (s or "").strip()
    if not _RX_HHMM.match(s):
        raise ValueError("bad_time")
    h, m = s.split(":")
    return f"{int(h):02d}:{int(m):02d}"

def _isod(s: str) -> str:
    s = (s or "").strip()
    if not _RX_ISOD.match(s):
        raise ValueError("bad_date")
    return s

def _coerce_ranges(val: Any) -> List[Tuple[str, str]]:
    if val is None:
        return []
    if isinstance(val, str):
        v = val.strip().lower()
        if not v or v == "closed":
            return []
        out: List[Tuple[str, str]] = []
        for part in re.split(r"\s*,\s*", v):
            m = re.match(r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$", part)
            if not m:
                raise ValueError(f"bad range: {part}")
            out.append((_hhmm(m.group(1)), _hhmm(m.group(2))))
        return out
    out: List[Tuple[str, str]] = []
    for r in (val or []):
        out.append((_hhmm(r.get("start", "")), _hhmm(r.get("end", ""))))
    return out

# ---------- UI opzionale ----------
@api_admin.get("/admin/schedule")
def admin_schedule_page():
    restaurant_id = request.args.get("rid", default=1, type=int)
    restaurant_name = request.args.get("name", default="Ristorante", type=str)
    return render_template("admin_schedule.html", restaurant_id=restaurant_id, restaurant_name=restaurant_name)

# ---------- Prenotazioni ----------
@api_admin.get("/api/admin-token/reservations")
def reservations_list():
    _auth()
    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    q = Reservation.query.filter(Reservation.restaurant_id == rid)

    date_s = (request.args.get("date") or "").strip()
    last_days = request.args.get("last_days", type=int)
    search = (request.args.get("q") or "").strip()

    if date_s:
        q = q.filter(Reservation.date == date_s)
    elif last_days:
        since = (datetime.now().date() - timedelta(days=last_days)).isoformat()
        q = q.filter(Reservation.date >= since)

    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                Reservation.name.ilike(like),
                Reservation.phone.ilike(like),
                Reservation.time.ilike(like),
            )
        )

    rows = q.order_by(Reservation.date.desc(), Reservation.time.asc(), Reservation.created_at.desc()).limit(500).all()
    items = [
        {
            "id": r.id,
            "restaurant_id": r.restaurant_id,
            "date": r.date,
            "time": r.time,
            "name": r.name,
            "phone": r.phone,
            "party_size": r.people,
            "status": getattr(r, "status", "confirmed"),
            "notes": getattr(r, "notes", "") or "",
        }
        for r in rows
    ]
    return jsonify({"ok": True, "items": items})

@api_admin.post("/api/admin-token/reservations/create")
def reservations_create():
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    name = (data.get("name") or data.get("customer_name") or "").strip()
    phone = (data.get("phone") or data.get("customer_phone") or "").strip()
    party = int(data.get("party_size") or data.get("people") or 0)
    date_s = _isod(data.get("date") or "")
    time_s = _hhmm(data.get("time") or "")
    status = (data.get("status") or "confirmed").strip()
    notes = (data.get("notes") or "").strip()

    if not name or party <= 0:
        return jsonify({"ok": False, "error": "bad_payload"}), 400

    try:
        r = Reservation(
            restaurant_id=rid,
            customer_name=name,
            customer_phone=phone,
            party_size=party,
            date=date_s,
            time=time_s,
            status=status,
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(r)
        db.session.commit()
        return jsonify({"ok": True, "id": r.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

# ---------- Stato (weekly + special + settings) ----------
@api_admin.get("/api/admin-token/schedule/state")
def schedule_state():
    _auth()
    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    weekly: List[List[Dict[str, str]]] = [[] for _ in range(7)]
    for oh in (
        OpeningHour.query.filter_by(restaurant_id=rid)
        .order_by(OpeningHour.weekday.asc(), OpeningHour.start_time.asc())
        .all()
    ):
        weekly[int(oh.weekday)].append({"start": str(oh.start_time)[:5], "end": str(oh.end_time)[:5]})

    s = RestaurantSetting.query.filter_by(restaurant_id=rid).first()
    settings = {
        "tz": (s.tz if s else "Europe/Rome"),
        "slot_step_min": (s.slot_step_min if s else 15),
        "last_order_min": (s.last_order_min if s else 15),
        "min_party": (s.min_party if s else 1),
        "max_party": (s.max_party if s else 12),
        "capacity_per_slot": (s.capacity_per_slot if s else 6),
    }

    by_date: Dict[str, Dict[str, Any]] = {}
    for sd in (
        SpecialDay.query.filter_by(restaurant_id=rid)
        .order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc().nullsfirst())
        .all()
    ):
        d = sd.date if isinstance(sd.date, str) else str(sd.date)
        ent = by_date.setdefault(d, {"date": d, "closed": False, "ranges": []})
        if sd.is_closed:
            ent["closed"] = True
            ent["ranges"] = []
        else:
            ent["ranges"].append({"start": str(sd.start_time)[:5], "end": str(sd.end_time)[:5]})

    return jsonify({"ok": True, "weekly": weekly, "special_days": list(by_date.values()), "settings": settings})

# ---------- Orari settimanali ----------
@api_admin.post("/api/admin-token/opening-hours/bulk")
def opening_hours_bulk():
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    try:
        if "weekday" in data:
            wd = int(data["weekday"])
            rngs = _coerce_ranges(data.get("ranges"))
            OpeningHour.query.filter_by(restaurant_id=rid, weekday=wd).delete()
            for a, b in rngs:
                db.session.add(OpeningHour(restaurant_id=rid, weekday=wd, start_time=a, end_time=b))
        elif "weekly" in data:
            weekly = data["weekly"] or {}
            OpeningHour.query.filter_by(restaurant_id=rid).delete()
            for k, arr in weekly.items():
                wd = int(k)
                for a, b in _coerce_ranges(arr):
                    db.session.add(OpeningHour(restaurant_id=rid, weekday=wd, start_time=a, end_time=b))
        else:
            return jsonify({"ok": False, "error": "bad_request", "detail": "weekday o weekly mancante"}), 400

        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

# ---------- Giorni speciali ----------
@api_admin.get("/api/admin-token/special-days/list")
def special_days_list():
    _auth()
    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    q = SpecialDay.query.filter_by(restaurant_id=rid).order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc().nullsfirst())
    by_date: Dict[str, Dict[str, Any]] = {}
    for sd in q.all():
        d = sd.date if isinstance(sd.date, str) else str(sd.date)
        ent = by_date.setdefault(d, {"restaurant_id": rid, "date": d, "closed": False, "ranges": []})
        if sd.is_closed:
            ent["closed"] = True
            ent["ranges"] = []
        else:
            ent["ranges"].append({"start": str(sd.start_time)[:5], "end": str(sd.end_time)[:5]})
    return jsonify({"ok": True, "items": list(by_date.values())})

@api_admin.post("/api/admin-token/special-days/upsert")
def special_days_upsert():
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400
    day = _isod(data.get("date") or "")
    closed = bool(data.get("is_closed", False))

    try:
        SpecialDay.query.filter_by(restaurant_id=rid, date=day).delete()
        if closed:
            db.session.add(SpecialDay(restaurant_id=rid, date=day, is_closed=True))
        else:
            for a, b in _coerce_ranges(data.get("ranges")):
                db.session.add(SpecialDay(restaurant_id=rid, date=day, is_closed=False, start_time=a, end_time=b))
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

@api_admin.post("/api/admin-token/special-days/delete")
def special_days_delete():
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    day = _isod(data.get("date") or "")
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400
    try:
        SpecialDay.query.filter_by(restaurant_id=rid, date=day).delete()
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

# ---------- Impostazioni ----------
@api_admin.post("/api/admin-token/settings/update")
def settings_update():
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    def _ival(x, default=None):
        try:
            return int(x)
        except Exception:
            return default

    try:
        s = RestaurantSetting.query.filter_by(restaurant_id=rid).first()
        if not s:
            s = RestaurantSetting(restaurant_id=rid)
            db.session.add(s)

        if "tz" in data:
            s.tz = (data.get("tz") or "").strip() or "Europe/Rome"
        if "slot_step_min" in data:
            s.slot_step_min = _ival(data.get("slot_step_min"), 15)
        if "last_order_min" in data:
            s.last_order_min = _ival(data.get("last_order_min"), 15)
        if "min_party" in data:
            s.min_party = _ival(data.get("min_party"), 1)
        if "max_party" in data:
            s.max_party = _ival(data.get("max_party"), 12)
        if "capacity_per_slot" in data:
            s.capacity_per_slot = _ival(data.get("capacity_per_slot"), 6)

        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

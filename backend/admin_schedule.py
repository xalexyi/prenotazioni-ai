# -*- coding: utf-8 -*-
# backend/admin_schedule.py — API gestionali (prenotazioni, orari, speciali, impostazioni)
from __future__ import annotations

import os
import re
from datetime import date as _date, datetime, time as _time, timedelta
from typing import List, Tuple, Dict, Any

from flask import Blueprint, request, jsonify, abort, render_template
from flask_login import current_user
from sqlalchemy import or_

from backend.models import db, Reservation
from backend.rules_service import OpeningHour, SpecialDay, RestaurantSetting

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()

api_admin = Blueprint("api_admin", __name__)

# ---------- Auth helper ----------
def _auth() -> None:
    tok = request.headers.get("X-Admin-Token") or request.args.get("token")
    if tok and tok == ADMIN_TOKEN:
        return
    # consentiamo anche l’owner loggato se il restaurant_id coincide
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
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _hhmm(s: str) -> str:
    if not _TIME_RE.match(str(s).strip()):
        raise ValueError("bad_time")
    hh, mm = str(s).split(":")
    return f"{int(hh):02d}:{int(mm):02d}"

def _to_time_or_str(s: str) -> Any:
    try:
        hh, mm = _hhmm(s).split(":")
        return _time(int(hh), int(mm))
    except Exception:
        return _hhmm(s)

def _to_date_or_str(s: str) -> Any:
    if not _DATE_RE.match(str(s).strip()):
        raise ValueError("bad_date")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return s

def parse_range_list(s: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if not s:
        return out
    for part in re.split(r"\s*,\s*", str(s).strip()):
        if not part:
            continue
        m = re.match(r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$", part)
        if not m:
            raise ValueError(f"bad range: {part}")
        out.append((_hhmm(m.group(1)), _hhmm(m.group(2))))
    return out

def _coerce_ranges(value: Any) -> List[Tuple[str, str]]:
    if value is None:
        return []
    if isinstance(value, str):
        if value.strip().lower() == "closed":
            return []
        return parse_range_list(value)
    out: List[Tuple[str, str]] = []
    for r in (value or []):
        a, b = (r.get("start"), r.get("end"))
        out.append((_hhmm(a), _hhmm(b)))
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
        return jsonify({"ok": False, "error": "missing RID"}), 400

    qry = Reservation.query.filter(Reservation.restaurant_id == rid)

    date_s = (request.args.get("date") or "").strip()
    last_days = request.args.get("last_days", type=int)
    q = (request.args.get("q") or "").strip()

    if date_s:
        qry = qry.filter(Reservation.date == date_s)
    elif last_days:
        since = (_date.today() - timedelta(days=last_days)).isoformat()
        qry = qry.filter(Reservation.date >= since)

    if q:
        like = f"%{q}%"
        qry = qry.filter(
            or_(
                Reservation.customer_name.ilike(like),
                getattr(Reservation, "phone").ilike(like),
                getattr(Reservation, "time").ilike(like),
            )
        )

    qry = qry.order_by(Reservation.date.desc(), Reservation.time.asc(), Reservation.created_at.desc())
    rows = qry.limit(500).all()

    items = []
    for r in rows:
        # date/time sono stringhe nel tuo modello
        d_str = r.date
        t_str = r.time
        phone = getattr(r, "phone", None)
        party = getattr(r, "party_size", None) or getattr(r, "people", None)

        items.append({
            "id": r.id,
            "restaurant_id": r.restaurant_id,
            "date": d_str,
            "time": t_str,
            "name": r.customer_name,
            "phone": phone,
            "party_size": party,
            "status": getattr(r, "status", "confirmed"),
            "notes": getattr(r, "notes", "") or "",
        })

    return jsonify({"ok": True, "items": items}), 200


@api_admin.post("/api/admin-token/reservations/create")
def reservations_create():
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    name  = (data.get("name") or data.get("customer_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    notes = (data.get("notes") or "").strip()
    status = (data.get("status") or "confirmed").strip()
    date_s = _hhmm("00:00")  # placeholder per validazione sotto
    date_s = (data.get("date") or "").strip()
    time_s = (data.get("time") or "").strip()

    if not name:
        return jsonify({"ok": False, "error": "missing_name"}), 400
    if not _DATE_RE.match(date_s):
        return jsonify({"ok": False, "error": "bad_date"}), 400
    if not _TIME_RE.match(time_s):
        return jsonify({"ok": False, "error": "bad_time"}), 400
    hh, mm = time_s.split(":")
    time_s = f"{int(hh):02d}:{mm}"

    party = int(data.get("party_size") or data.get("people") or 0)
    if party <= 0:
        return jsonify({"ok": False, "error": "bad_party"}), 400

    try:
        r = Reservation(
            restaurant_id=rid,
            customer_name=name,
            date=date_s,   # nel tuo modello è str
            time=time_s,   # nel tuo modello è str
        )
        # mappature schema
        if hasattr(Reservation, "party_size"):
            r.party_size = party
        if hasattr(Reservation, "people"):
            r.people = party
        if hasattr(Reservation, "status"):
            r.status = status or "confirmed"
        if hasattr(Reservation, "notes"):
            r.notes = notes
        if hasattr(Reservation, "phone"):
            r.phone = phone

        db.session.add(r)
        db.session.commit()
        return jsonify({"ok": True, "id": r.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

# ---------- STATE ----------
@api_admin.get("/api/admin-token/schedule/state")
def schedule_state():
    _auth()
    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        return jsonify({"ok": False, "error": "restaurant_id obbligatorio"}), 400

    weekly: List[List[Dict[str, str]]] = [[] for _ in range(7)]
    for oh in OpeningHour.query.filter_by(restaurant_id=rid).order_by(OpeningHour.weekday.asc(), OpeningHour.start_time.asc()).all():
        s = oh.start_time; e = oh.end_time
        s_str = s if isinstance(s, str) else (s.strftime("%H:%M") if hasattr(s, "strftime") else str(s)[:5])
        e_str = e if isinstance(e, str) else (e.strftime("%H:%M") if hasattr(e, "strftime") else str(e)[:5])
        weekly[int(oh.weekday)].append({"start": s_str, "end": e_str})

    s = RestaurantSetting.query.filter_by(restaurant_id=rid).first()
    settings = {
        "tz": s.tz if s else "Europe/Rome",
        "slot_step_min": s.slot_step_min if s else 15,
        "last_order_min": s.last_order_min if s else 15,
        "min_party": s.min_party if s else 1,
        "max_party": s.max_party if s else 12,
        "capacity_per_slot": s.capacity_per_slot if s else 6,
    }

    by_date: Dict[str, Dict[str, Any]] = {}
    for sd in SpecialDay.query.filter_by(restaurant_id=rid).order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc()).all():
        d = sd.date if isinstance(sd.date, str) else (sd.date.isoformat() if hasattr(sd.date, "isoformat") else str(sd.date))
        ent = by_date.setdefault(d, {"date": d, "closed": False, "ranges": []})
        if sd.is_closed:
            ent["closed"] = True
            ent["ranges"] = []
        else:
            s = sd.start_time; e = sd.end_time
            s_str = s if isinstance(s, str) else (s.strftime("%H:%M") if hasattr(s, "strftime") else str(s)[:5])
            e_str = e if isinstance(e, str) else (e.strftime("%H:%M") if hasattr(e, "strftime") else str(e)[:5])
            ent["ranges"].append({"start": s_str, "end": e_str})

    return jsonify({"ok": True, "weekly": weekly, "special_days": list(by_date.values()), "settings": settings})

# ---------- WEEKLY ----------
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
                db.session.add(OpeningHour(restaurant_id=rid, weekday=wd, start_time=_to_time_or_str(a), end_time=_to_time_or_str(b)))
        elif "weekly" in data:
            weekly = data["weekly"] or {}
            OpeningHour.query.filter_by(restaurant_id=rid).delete()
            for k, arr in weekly.items():
                wd = int(k)
                for a, b in _coerce_ranges(arr):
                    db.session.add(OpeningHour(restaurant_id=rid, weekday=wd, start_time=_to_time_or_str(a), end_time=_to_time_or_str(b)))
        else:
            return jsonify({"ok": False, "error": "bad_request", "detail": "weekday o weekly mancante"}), 400
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

# ---------- SPECIAL DAYS ----------
@api_admin.get("/api/admin-token/special-days/list")
def special_days_list():
    _auth()
    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        return jsonify({"ok": False, "error": "restaurant_id obbligatorio"}), 400

    q = SpecialDay.query.filter_by(restaurant_id=rid).order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc())
    by_date: Dict[str, Dict[str, Any]] = {}
    for sd in q.all():
        d = sd.date if isinstance(sd.date, str) else (sd.date.isoformat() if hasattr(sd.date, "isoformat") else str(sd.date))
        ent = by_date.setdefault(d, {"restaurant_id": rid, "date": d, "closed": False, "ranges": []})
        if sd.is_closed:
            ent["closed"] = True
            ent["ranges"] = []
        else:
            s = sd.start_time; e = sd.end_time
            s_str = s if isinstance(s, str) else (s.strftime("%H:%M") if hasattr(s, "strftime") else str(s)[:5])
            e_str = e if isinstance(e, str) else (e.strftime("%H:%M") if hasattr(e, "strftime") else str(e)[:5])
            ent["ranges"].append({"start": s_str, "end": e_str})
    return jsonify({"ok": True, "items": list(by_date.values())})

@api_admin.post("/api/admin-token/special-days/upsert")
def special_days_upsert():
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400
    day = (data.get("date") or "").strip()
    if not _DATE_RE.match(day):
        return jsonify({"ok": False, "error": "bad_date"}), 400
    closed = bool(data.get("is_closed", False))
    try:
        SpecialDay.query.filter_by(restaurant_id=rid, date=_to_date_or_str(day)).delete()
        if closed:
            db.session.add(SpecialDay(restaurant_id=rid, date=_to_date_or_str(day), is_closed=True))
        else:
            for a, b in _coerce_ranges(data.get("ranges")):
                db.session.add(SpecialDay(restaurant_id=rid, date=_to_date_or_str(day), is_closed=False, start_time=_to_time_or_str(a), end_time=_to_time_or_str(b)))
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
    day = (data.get("date") or "").strip()
    if not rid or not _DATE_RE.match(day):
        return jsonify({"ok": False, "error": "bad_request"}), 400
    try:
        SpecialDay.query.filter_by(restaurant_id=rid, date=_to_date_or_str(day)).delete()
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

# ---------- SETTINGS ----------
@api_admin.post("/api/admin-token/settings/update")
def settings_update():
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400
    try:
        s = RestaurantSetting.query.filter_by(restaurant_id=rid).first() or RestaurantSetting(restaurant_id=rid)
        if "tz" in data and data["tz"] is not None:
            s.tz = str(data["tz"]).strip() or "Europe/Rome"
        for k in ["slot_step_min", "last_order_min", "min_party", "max_party", "capacity_per_slot"]:
            if k in data and data[k] is not None:
                setattr(s, k, int(data[k]))
        db.session.add(s)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

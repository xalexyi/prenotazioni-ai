# -*- coding: utf-8 -*-
# backend/admin_schedule.py

import os
import re
from datetime import date as _date, datetime, time as _time, timedelta
from typing import List, Tuple, Dict, Any, Optional

from flask import Blueprint, request, jsonify, abort, render_template
from sqlalchemy import or_

from backend.models import db, Reservation
from backend.rules_service import OpeningHour, SpecialDay, RestaurantSetting

# =======================
# Config / Auth
# =======================
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

api_admin = Blueprint("api_admin", __name__)

def _auth() -> None:
    """Autenticazione tramite X-Admin-Token (o ?token=...)."""
    tok = request.headers.get("X-Admin-Token") or request.args.get("token")
    if not tok or tok != ADMIN_TOKEN:
        abort(401, description="unauthorized")


# =======================
# Pagina admin (UI opzionale)
# =======================
@api_admin.get("/admin/schedule")
def admin_schedule_page():
    restaurant_id = request.args.get("rid", default=1, type=int)
    restaurant_name = request.args.get("name", default="Ristorante", type=str)
    return render_template(
        "admin_schedule.html",
        restaurant_id=restaurant_id,
        restaurant_name=restaurant_name,
    )


# =======================
# Utils
# =======================
WEEKMAP: Dict[str, int] = {
    "mon": 0, "monday": 0, "lun": 0, "lunedì": 0, "lunedi": 0,
    "tue": 1, "tuesday": 1, "mar": 1, "martedì": 1, "martedi": 1,
    "wed": 2, "wednesday": 2, "mer": 2, "mercoledì": 2, "mercoledi": 2,
    "thu": 3, "thursday": 3, "gio": 3, "giovedì": 3, "giovedi": 3,
    "fri": 4, "friday": 4, "ven": 4, "venerdì": 4, "venerdi": 4,
    "sat": 5, "saturday": 5, "sab": 5, "sabato": 5,
    "sun": 6, "sunday": 6, "dom": 6, "domenica": 6,
}

_TIME_RE = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _hhmm(s: str) -> str:
    """Normalizza 'H:MM' -> 'HH:MM' e valida."""
    s = (s or "").strip()
    if not s:
        raise ValueError("empty time")
    if not _TIME_RE.match(s):
        raise ValueError(f"invalid time: {s} (use HH:MM)")
    h, m = s.split(":")
    return f"{int(h):02d}:{m}"

def _to_time_or_str(s: str):
    """Ritorna datetime.time('HH:MM') se possibile, altrimenti stringa HH:MM."""
    try:
        hhmm = _hhmm(s)
        h, m = map(int, hhmm.split(":"))
        return _time(hour=h, minute=m)
    except Exception:
        return _hhmm(s)

def _to_date_or_str(s: str):
    """Ritorna datetime.date se possibile, altrimenti stringa YYYY-MM-DD."""
    s = (s or "").strip()
    if not _DATE_RE.match(s):
        raise ValueError("bad_date")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return s

def parse_range_list(s: str) -> List[Tuple[str, str]]:
    """
    "12:00-15:00,19:00-23:30" -> [("12:00","15:00"), ("19:00","23:30")]
    """
    out: List[Tuple[str, str]] = []
    if s is None:
        return out
    raw = str(s).strip()
    if not raw:
        return out
    for part in re.split(r"\s*,\s*", raw):
        if not part:
            continue
        m = re.match(r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$", part)
        if not m:
            raise ValueError(f"bad range: {part}")
        a, b = _hhmm(m.group(1)), _hhmm(m.group(2))
        out.append((a, b))
    return out

def _coerce_ranges(value: Any) -> List[Tuple[str, str]]:
    """
    Accetta:
      - stringa "12:00-15:00,19:00-23:30"
      - lista di stringhe ["12:00-15:00", "19:00-23:30"]
      - lista di tuple/array ["12:00","15:00"]
    e ritorna lista di tuple (start, end) validate HH:MM.
    """
    if value is None:
        return []
    if isinstance(value, str):
        if value.strip().lower() == "closed":
            return []
        return parse_range_list(value)

    ranges: List[Tuple[str, str]] = []
    for s in value:
        if not s:
            continue
        if isinstance(s, str):
            if "-" not in s:
                raise ValueError(f"bad range: {s}")
            a, b = s.split("-", 1)
            a, b = _hhmm(a), _hhmm(b)
        else:
            try:
                a, b = s
                a, b = _hhmm(a), _hhmm(b)
            except Exception:
                raise ValueError(f"bad range: {s}")
        ranges.append((a, b))
    return ranges


# =======================
# RESERVATIONS (filtri lista)
# =======================
@api_admin.get("/api/admin-token/reservations")
def admin_reservations_list():
    """
    Filtra le prenotazioni dell'admin.

    Query:
      - restaurant_id (obbligatorio)
      - date=YYYY-MM-DD   (filtra esattamente quel giorno)
      - today=1           (ignora 'date' e forza oggi)
      - last_days=30      (prenotazioni con date >= oggi-30)
      - q=string          (ricerca su name/phone/notes)
    """
    _auth()
    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        return jsonify({"ok": False, "error": "restaurant_id obbligatorio"}), 400

    qtext = (request.args.get("q") or "").strip()
    day_str = (request.args.get("date") or "").strip()
    last_days = request.args.get("last_days", type=int)
    today_flag = str(request.args.get("today") or "").lower() in ("1", "true", "yes", "y")

    qry = Reservation.query.filter(Reservation.restaurant_id == rid)

    if qtext:
        like = f"%{qtext}%"
        filters = [Reservation.customer_name.ilike(like)]
        if hasattr(Reservation, "customer_phone"):
            filters.append(Reservation.customer_phone.ilike(like))
        if hasattr(Reservation, "phone"):
            filters.append(Reservation.phone.ilike(like))
        if hasattr(Reservation, "notes"):
            filters.append(Reservation.notes.ilike(like))
        if hasattr(Reservation, "time"):
            filters.append(Reservation.time.cast(db.String).ilike(like))
        qry = qry.filter(or_(*filters))

    if today_flag:
        d = _date.today()
        qry = qry.filter(Reservation.date == d)
    elif day_str:
        if not _DATE_RE.match(day_str):
            return jsonify({"ok": False, "error": "Formato data non valido (YYYY-MM-DD)"}), 400
        d = datetime.strptime(day_str, "%Y-%m-%d").date()
        qry = qry.filter(Reservation.date == d)
    elif last_days:
        since = _date.today() - timedelta(days=last_days)
        qry = qry.filter(Reservation.date >= since)

    qry = qry.order_by(Reservation.date.desc(), Reservation.time.asc(), Reservation.created_at.desc())
    rows = qry.limit(500).all()

    items = []
    for r in rows:
        d_str = r.date.isoformat() if getattr(r, "date", None) and hasattr(r.date, "isoformat") else (str(r.date) if getattr(r, "date", None) else None)
        if getattr(r, "time", None) is None:
            t_str = None
        else:
            if hasattr(r.time, "strftime"):
                t_str = r.time.strftime("%H:%M")
            else:
                t = str(r.time)
                t_str = t[:5] if len(t) >= 5 else t

        phone = getattr(r, "customer_phone", None) or getattr(r, "phone", None)
        party = getattr(r, "party_size", None) or getattr(r, "people", None)

        items.append({
            "id": r.id,
            "restaurant_id": r.restaurant_id,
            "date": d_str,
            "time": t_str,
            "name": r.customer_name,
            "phone": phone,
            "party_size": party,
            "notes": getattr(r, "notes", None),
            "status": getattr(r, "status", None),
            "source": getattr(r, "source", None),
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) and hasattr(r.created_at, "isoformat") else None,
            "date_time": f"{d_str} {t_str}" if (d_str and t_str) else None,
        })

    return jsonify({"ok": True, "items": items}), 200


# ============ CREA PRENOTAZIONE (NEW) ============
@api_admin.post("/api/admin-token/reservations/create")
def reservations_create():
    """
    Crea una prenotazione manuale dalla dashboard.
    Body JSON:
      { restaurant_id, date:"YYYY-MM-DD", time:"HH:MM",
        name, phone, party_size, status?, notes? }
    """
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    name  = (data.get("name") or data.get("customer_name") or "").strip()
    phone = (data.get("phone") or data.get("customer_phone") or "").strip()
    notes = (data.get("notes") or "").strip()
    status = (data.get("status") or "confirmed").strip()
    date_s = (data.get("date") or "").strip()
    time_s = (data.get("time") or "").strip()

    if not name:
        return jsonify({"ok": False, "error": "missing_name"}), 400
    if not date_s or not _DATE_RE.match(date_s):
        return jsonify({"ok": False, "error": "bad_date"}), 400
    if not _TIME_RE.match(time_s):
        return jsonify({"ok": False, "error": "bad_time"}), 400
    hh, mm = time_s.split(":")
    time_s = f"{int(hh):02d}:{mm}"

    party = int(data.get("party_size") or data.get("people") or 0)
    if party <= 0:
        return jsonify({"ok": False, "error": "bad_party"}), 400

    # compat con schema variabile
    r = Reservation(
        restaurant_id=rid,
        customer_name=name,
        date=_to_date_or_str(date_s),
        time=_to_time_or_str(time_s),
        source="manual",
    )
    if hasattr(Reservation, "customer_phone"):
        r.customer_phone = phone
    if hasattr(Reservation, "phone"):
        r.phone = phone
    if hasattr(Reservation, "party_size"):
        r.party_size = party
    if hasattr(Reservation, "people"):
        r.people = party
    if hasattr(Reservation, "status"):
        r.status = status or "confirmed"
    if hasattr(Reservation, "notes"):
        r.notes = notes

    db.session.add(r)
    db.session.commit()
    return jsonify({"ok": True, "id": r.id}), 201


# =======================
# STATE (weekly + settings + special days)
# =======================
@api_admin.get("/api/admin-token/schedule/state")
def schedule_state():
    _auth()
    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        return jsonify({"ok": False, "error": "restaurant_id obbligatorio"}), 400

    # Weekly
    weekly: List[List[Dict[str, str]]] = [[] for _ in range(7)]
    for oh in OpeningHour.query.filter_by(restaurant_id=rid).order_by(OpeningHour.weekday.asc(), OpeningHour.start_time.asc()).all():
        s = oh.start_time
        e = oh.end_time
        s_str = s.strftime("%H:%M") if hasattr(s, "strftime") else str(s)[:5]
        e_str = e.strftime("%H:%M") if hasattr(e, "strftime") else str(e)[:5]
        weekly[int(oh.weekday)].append({"start": s_str, "end": e_str})

    # Settings
    s = RestaurantSetting.query.filter_by(restaurant_id=rid).first()
    settings = {
        "tz": s.tz if s else "Europe/Rome",
        "slot_step_min": s.slot_step_min if s else 15,
        "last_order_min": s.last_order_min if s else 15,
        "min_party": s.min_party if s else 1,
        "max_party": s.max_party if s else 12,
        "capacity_per_slot": s.capacity_per_slot if s else 6,
    }

    # Special days
    q = SpecialDay.query.filter_by(restaurant_id=rid).order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc())
    by_date: Dict[str, Dict[str, Any]] = {}
    for sd in q.all():
        dd = sd.date.isoformat() if hasattr(sd.date, "isoformat") else str(sd.date)
        ent = by_date.setdefault(dd, {"date": dd, "closed": False, "ranges": []})
        if sd.is_closed:
            ent["closed"] = True
            ent["ranges"] = []
        else:
            s = sd.start_time
            e = sd.end_time
            s_str = s.strftime("%H:%M") if hasattr(s, "strftime") else str(s)[:5]
            e_str = e.strftime("%H:%M") if hasattr(e, "strftime") else str(e)[:5]
            ent["ranges"].append({"start": s_str, "end": e_str})

    return jsonify({"ok": True, "weekly": weekly, "settings": settings, "special_days": list(by_date.values())}), 200


# =======================
# OPENING HOURS (bulk replace per weekday)
# =======================
@api_admin.post("/api/admin-token/opening-hours/bulk")
def opening_hours_bulk():
    """
    JSON:
    {
      "restaurant_id": 1,
      "weekday": "mon" | 0..6,
      "ranges": "12:00-15:00,19:00-23:30" | ["12:00-15:00", ...] | [["12:00","15:00"], ...] | "CLOSED"
    }
    """
    _auth()
    data = request.get_json(force=True, silent=True) or {}

    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    wd = data.get("weekday", None)
    try:
        if isinstance(wd, str):
            wd_key = wd.strip().lower()
            if wd_key not in WEEKMAP:
                return jsonify({"ok": False, "error": "bad_weekday"}), 400
            weekday = WEEKMAP[wd_key]
        else:
            weekday = int(wd)
    except Exception:
        return jsonify({"ok": False, "error": "bad_weekday"}), 400

    if weekday < 0 or weekday > 6:
        return jsonify({"ok": False, "error": "bad_weekday"}), 400

    try:
        ranges = _coerce_ranges(data.get("ranges"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    try:
        with db.session.begin():
            db.session.query(OpeningHour).filter_by(restaurant_id=rid, weekday=weekday).delete()
            for a, b in ranges:
                db.session.add(
                    OpeningHour(
                        restaurant_id=rid,
                        weekday=weekday,
                        start_time=_to_time_or_str(a),
                        end_time=_to_time_or_str(b),
                    )
                )
        return jsonify({"ok": True, "weekday": weekday, "count": len(ranges)}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500


# =======================
# SPECIAL DAYS
# =======================
@api_admin.get("/api/admin-token/special-days/list")
def special_days_list():
    _auth()
    rid = request.args.get("restaurant_id", type=int)
    if not rid:
        return jsonify({"ok": False, "error": "restaurant_id obbligatorio"}), 400

    q = SpecialDay.query.filter_by(restaurant_id=rid).order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc())
    by_date: Dict[str, Dict[str, Any]] = {}
    for sd in q.all():
        d = sd.date.isoformat() if hasattr(sd.date, "isoformat") else str(sd.date)
        ent = by_date.setdefault(d, {"restaurant_id": rid, "date": d, "closed": False, "ranges": []})
        if sd.is_closed:
            ent["closed"] = True
            ent["ranges"] = []
        else:
            s = sd.start_time
            e = sd.end_time
            s_str = s.strftime("%H:%M") if hasattr(s, "strftime") else str(s)[:5]
            e_str = e.strftime("%H:%M") if hasattr(e, "strftime") else str(e)[:5]
            ent["ranges"].append({"start": s_str, "end": e_str})
    return jsonify({"ok": True, "items": list(by_date.values())}), 200


@api_admin.post("/api/admin-token/special-days/upsert")
def special_days_upsert():
    _auth()
    data = request.get_json(force=True, silent=True) or {}

    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    date_s = (data.get("date") or "").strip()
    if not date_s or not _DATE_RE.match(date_s):
        return jsonify({"ok": False, "error": "bad_date"}), 400

    closed = bool(data.get("closed"))
    if closed:
        ranges: List[Tuple[str, str]] = []
    else:
        try:
            ranges = _coerce_ranges(data.get("ranges"))
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    try:
        with db.session.begin():
            db.session.query(SpecialDay).filter_by(restaurant_id=rid, date=_to_date_or_str(date_s)).delete()
            if closed:
                db.session.add(SpecialDay(restaurant_id=rid, date=_to_date_or_str(date_s), is_closed=True))
            else:
                for a, b in ranges:
                    db.session.add(
                        SpecialDay(
                            restaurant_id=rid,
                            date=_to_date_or_str(date_s),
                            is_closed=False,
                            start_time=_to_time_or_str(a),
                            end_time=_to_time_or_str(b),
                        )
                    )
        return jsonify({"ok": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500


@api_admin.post("/api/admin-token/special-days/delete")
def special_days_delete():
    _auth()
    data = request.get_json(force=True, silent=True) or {}

    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400

    date_s = (data.get("date") or "").strip()
    if not date_s or not _DATE_RE.match(date_s):
        return jsonify({"ok": False, "error": "bad_date"}), 400

    try:
        with db.session.begin():
            db.session.query(SpecialDay).filter_by(restaurant_id=rid, date=_to_date_or_str(date_s)).delete()
        return jsonify({"ok": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500


# =======================
# SETTINGS
# =======================
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
        return jsonify({"ok": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500


# =======================
# COMANDI testuali (compat)
# =======================
@api_admin.post("/api/admin-token/schedule/commands")
def schedule_commands():
    _auth()
    if request.is_json:
        data = request.get_json() or {}
        text = (data.get("commands") or "").strip()
    else:
        text = (request.get_data(as_text=True) or "").strip()

    rid: Optional[int] = None
    ops: List[Tuple] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        u = line.lower()

        m = re.match(r"^rid\s*=\s*(\d+)$", u)
        if m:
            rid = int(m.group(1))
            continue

        m = re.match(r"^week\s+([a-zàèéìòù]+)\s+(.+)$", u)
        if m:
            wdkey = m.group(1)
            val = m.group(2).strip()
            if wdkey not in WEEKMAP:
                return jsonify({"ok": False, "error": f"bad weekday: {wdkey}"}), 400
            weekday = WEEKMAP[wdkey]
            if val == "closed":
                ops.append(("WEEK_REPLACE", weekday, []))
            else:
                try:
                    rngs = parse_range_list(val)
                except Exception as e:
                    return jsonify({"ok": False, "error": str(e)}), 400
                ops.append(("WEEK_REPLACE", weekday, rngs))
            continue

        m = re.match(r"^special\s+(\d{4}-\d{2}-\d{2})\s+(.+)$", u)
        if m:
            date_s = m.group(1)
            if not _DATE_RE.match(date_s):
                return jsonify({"ok": False, "error": "bad_date"}), 400
            val = m.group(2).strip()
            if val == "closed":
                ops.append(("SPECIAL_REPLACE", date_s, "closed", []))
            else:
                try:
                    rngs = parse_range_list(val)
                except Exception as e:
                    return jsonify({"ok": False, "error": str(e)}), 400
                ops.append(("SPECIAL_REPLACE", date_s, "open", rngs))
            continue

        m = re.match(r"^settings\s+(.+)$", u)
        if m:
            kv = m.group(1)
            args = dict(re.findall(r"([a-z]+)=([^\s]+)", kv))
            ops.append(("SETTINGS", args))
            continue

        return jsonify({"ok": False, "error": f"bad command: {line}"}), 400

    if not rid:
        return jsonify({"ok": False, "error": "missing RID=..."}), 400

    try:
        with db.session.begin():
            for op in ops:
                if op[0] == "WEEK_REPLACE":
                    weekday, rngs = op[1], op[2]
                    db.session.query(OpeningHour).filter_by(restaurant_id=rid, weekday=weekday).delete()
                    for a, b in rngs:
                        db.session.add(
                            OpeningHour(
                                restaurant_id=rid,
                                weekday=weekday,
                                start_time=_to_time_or_str(a),
                                end_time=_to_time_or_str(b),
                            )
                        )

                elif op[0] == "SPECIAL_REPLACE":
                    date_s, mode, rngs = op[1], op[2], op[3]
                    db.session.query(SpecialDay).filter_by(restaurant_id=rid, date=_to_date_or_str(date_s)).delete()
                    if mode == "closed":
                        db.session.add(SpecialDay(restaurant_id=rid, date=_to_date_or_str(date_s), is_closed=True))
                    else:
                        for a, b in rngs:
                            db.session.add(
                                SpecialDay(
                                    restaurant_id=rid,
                                    date=_to_date_or_str(date_s),
                                    is_closed=False,
                                    start_time=_to_time_or_str(a),
                                    end_time=_to_time_or_str(b),
                                )
                            )

                elif op[0] == "SETTINGS":
                    args = op[1]
                    s = RestaurantSetting.query.filter_by(restaurant_id=rid).first() or RestaurantSetting(restaurant_id=rid)
                    if "step" in args: s.slot_step_min = int(args["step"])
                    if "last" in args: s.last_order_min = int(args["last"])
                    if "capacity" in args: s.capacity_per_slot = int(args["capacity"])
                    if "tz" in args: s.tz = args["tz"]
                    if "party" in args:
                        m2 = re.match(r"^(\d+)-(\d+)$", args["party"])
                        if m2:
                            s.min_party = int(m2.group(1))
                            s.max_party = int(m2.group(2))
                    db.session.add(s)

        return jsonify({"ok": True, "restaurant_id": rid, "ops": len(ops)}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

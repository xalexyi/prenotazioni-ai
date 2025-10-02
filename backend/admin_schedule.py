# -*- coding: utf-8 -*-
# backend/admin_schedule.py
from __future__ import annotations

import os
import re
from datetime import datetime, date as _date, timedelta
from typing import Any, Dict, List, Tuple

from flask import Blueprint, request, jsonify, abort
from flask_login import current_user, login_required

from backend.models import (
    db,
    Restaurant,
    Reservation,
    OpeningHour,
    SpecialDay,
    RestaurantSetting,
)

# =========================================================
# Blueprint: tutte le rotte amministrative con admin token
# =========================================================
api_admin = Blueprint("api_admin_token", __name__, url_prefix="/api/admin-token")

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()


# ----------------------------
# Utils / sicurezza
# ----------------------------
_HHMM_RE = re.compile(r"^\d{1,2}:\d{2}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _assert_admin_or_owner(restaurant_id: int | None) -> int:
    """
    Autorizzazione:
      - Se presente header X-Admin-Token uguale a ADMIN_TOKEN => OK
      - Altrimenti, se l'utente è loggato e il suo id coincide con restaurant_id => OK
    """
    tok = request.headers.get("X-Admin-Token")
    if tok and ADMIN_TOKEN and tok == ADMIN_TOKEN:
        return int(restaurant_id or 0)

    # fallback: utente loggato (flask-login)
    if getattr(current_user, "is_authenticated", False):
        rid_user = getattr(current_user, "id", None) or getattr(current_user, "restaurant_id", None)
        if restaurant_id is None or int(rid_user or 0) == int(restaurant_id or 0):
            return int(rid_user or restaurant_id or 0)

    abort(401, description="unauthorized")


def _rid_from_request() -> int:
    rid = request.args.get("restaurant_id", type=int)
    if rid is None and request.is_json:
        body = request.get_json(silent=True) or {}
        rid = body.get("restaurant_id")
    if rid is None:
        abort(400, description="restaurant_id mancante")
    return _assert_admin_or_owner(int(rid))


def _is_hhmm(s: str) -> bool:
    return bool(_HHMM_RE.match((s or "").strip()))


def _is_iso_date(s: str) -> bool:
    return bool(_ISO_DATE_RE.match((s or "").strip()))


def _parse_ranges(raw: List[Dict[str, str]] | None) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for r in raw or []:
        a, b = (r.get("start", "").strip(), r.get("end", "").strip())
        if not (_is_hhmm(a) and _is_hhmm(b)):
            raise ValueError(f"Intervallo non valido: '{a}-{b}' (usa HH:MM)")
        out.append((a, b))
    return out


# ----------------------------
# STATO / riepilogo
# ----------------------------
@api_admin.get("/schedule/state")
@login_required
def schedule_state():
    rid = _rid_from_request()

    # Weekly
    weekly_rows = (
        OpeningHour.query.filter_by(restaurant_id=rid)
        .order_by(OpeningHour.weekday.asc(), OpeningHour.start_time.asc())
        .all()
    )
    weekly = [{"weekday": r.weekday, "ranges": [{"start": r.start_time, "end": r.end_time}]} for r in weekly_rows]

    # Special days (aggregati per data)
    sp_rows = (
        SpecialDay.query.filter_by(restaurant_id=rid)
        .order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc().nullsfirst())
        .all()
    )
    specials: Dict[str, Dict[str, Any]] = {}
    for s in sp_rows:
        if s.date not in specials:
            specials[s.date] = {"date": s.date, "is_closed": bool(s.is_closed), "ranges": []}
        if not s.is_closed and s.start_time and s.end_time:
            specials[s.date]["ranges"].append({"start": s.start_time, "end": s.end_time})
        if s.is_closed:
            specials[s.date]["is_closed"] = True
            specials[s.date]["ranges"] = []

    # Settings
    st = RestaurantSetting.query.filter_by(restaurant_id=rid).first()
    settings = {
        "tz": st.tz if st else None,
        "slot_step_min": st.slot_step_min if st else None,
        "last_order_min": st.last_order_min if st else None,
        "min_party": st.min_party if st else None,
        "max_party": st.max_party if st else None,
        "capacity_per_slot": st.capacity_per_slot if st else None,
    }

    # KPI semplici (oggi)
    today = datetime.now().date().isoformat()
    res_today = (
        Reservation.query.filter_by(restaurant_id=rid, date=today)
        .order_by(Reservation.time.asc())
        .all()
    )
    kpi_today = len(res_today)

    return jsonify(
        {
            "ok": True,
            "weekly": weekly,
            "special_days": list(specials.values()),
            "settings": settings,
            "kpi": {"today": kpi_today},
        }
    )


# ----------------------------
# ORARI SETTIMANALI (bulk)
# ----------------------------
@api_admin.post("/opening-hours/bulk")
@login_required
def opening_hours_bulk():
    """
    Accetta sia:
      A) { restaurant_id, weekday, ranges: [{start,end}, ...] }  (chiamato più volte dal client)
      B) { restaurant_id, weekly: { "0":[{..}], ... "6":[{..}] } } (tutto insieme)
    Sovrascrive le righe esistenti per quel weekday (o per tutti se weekly intero).
    """
    rid = _rid_from_request()
    data = request.get_json(force=True, silent=True) or {}

    try:
        ops = []

        if "weekday" in data:
            wd = int(data["weekday"])
            ranges = _parse_ranges(data.get("ranges"))
            OpeningHour.query.filter_by(restaurant_id=rid, weekday=wd).delete(synchronize_session=False)
            for a, b in ranges:
                db.session.add(OpeningHour(restaurant_id=rid, weekday=wd, start_time=a, end_time=b))
            ops.append(("weekday", wd, len(ranges)))

        elif "weekly" in data:
            weekly = data["weekly"] or {}
            # cancelliamo tutto e riscriviamo
            OpeningHour.query.filter_by(restaurant_id=rid).delete(synchronize_session=False)
            for k, arr in weekly.items():
                wd = int(k)
                ranges = _parse_ranges(arr)
                for a, b in ranges:
                    db.session.add(OpeningHour(restaurant_id=rid, weekday=wd, start_time=a, end_time=b))
            ops.append(("weekly", "all", "ok"))

        else:
            return jsonify({"ok": False, "error": "bad_request", "detail": "weekday o weekly mancante"}), 400

        db.session.commit()
        return jsonify({"ok": True, "ops": ops})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500


# ----------------------------
# GIORNI SPECIALI
# ----------------------------
@api_admin.get("/special-days/list")
@login_required
def special_days_list():
    rid = _rid_from_request()
    rows = (
        SpecialDay.query.filter_by(restaurant_id=rid)
        .order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc().nullsfirst())
        .all()
    )
    out: Dict[str, Dict[str, Any]] = {}
    for s in rows:
        if s.date not in out:
            out[s.date] = {"date": s.date, "is_closed": bool(s.is_closed), "ranges": []}
        if s.is_closed:
            out[s.date]["is_closed"] = True
            out[s.date]["ranges"] = []
        else:
            if s.start_time and s.end_time:
                out[s.date]["ranges"].append({"start": s.start_time, "end": s.end_time})
    return jsonify({"ok": True, "items": list(out.values())})


@api_admin.post("/special-days/upsert")
@login_required
def special_days_upsert():
    """
    Body:
      { restaurant_id, date:"YYYY-MM-DD", is_closed:bool, ranges:[{start,end}] }
    Se is_closed=True → scrive una sola riga chiusa (e rimuove eventuali aperture).
    Se is_closed=False → rimuove tutte le righe del giorno e inserisce le nuove fasce.
    """
    rid = _rid_from_request()
    data = request.get_json(force=True, silent=True) or {}
    day = (data.get("date") or "").strip()
    if not _is_iso_date(day):
        return jsonify({"ok": False, "error": "bad_date"}), 400

    is_closed = bool(data.get("is_closed", False))
    try:
        SpecialDay.query.filter_by(restaurant_id=rid, date=day).delete(synchronize_session=False)
        if is_closed:
            db.session.add(SpecialDay(restaurant_id=rid, date=day, is_closed=True))
        else:
            ranges = _parse_ranges(data.get("ranges"))
            if not ranges:
                return jsonify({"ok": False, "error": "ranges_required"}), 400
            for a, b in ranges:
                db.session.add(
                    SpecialDay(restaurant_id=rid, date=day, is_closed=False, start_time=a, end_time=b)
                )
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500


@api_admin.post("/special-days/delete")
@login_required
def special_days_delete():
    rid = _rid_from_request()
    data = request.get_json(force=True, silent=True) or {}
    day = (data.get("date") or "").strip()
    if not _is_iso_date(day):
        return jsonify({"ok": False, "error": "bad_date"}), 400
    try:
        SpecialDay.query.filter_by(restaurant_id=rid, date=day).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500


# ----------------------------
# IMPOSTAZIONI
# ----------------------------
@api_admin.post("/settings/update")
@login_required
def settings_update():
    rid = _rid_from_request()
    data = request.get_json(force=True, silent=True) or {}

    # normalizza
    def _ival(x, default=None):
        try:
            return int(x)
        except Exception:
            return default

    try:
        row = RestaurantSetting.query.filter_by(restaurant_id=rid).first()
        if not row:
            row = RestaurantSetting(restaurant_id=rid)
            db.session.add(row)

        if "tz" in data:
            row.tz = (data.get("tz") or "").strip() or None
        if "slot_step_min" in data:
            row.slot_step_min = _ival(data.get("slot_step_min"))
        if "last_order_min" in data:
            row.last_order_min = _ival(data.get("last_order_min"))
        if "min_party" in data:
            row.min_party = _ival(data.get("min_party"))
        if "max_party" in data:
            row.max_party = _ival(data.get("max_party"))
        if "capacity_per_slot" in data:
            row.capacity_per_slot = _ival(data.get("capacity_per_slot"))

        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500


# ----------------------------
# PRENOTAZIONI (lista/crea)
# ----------------------------
@api_admin.get("/reservations")
@login_required
def reservations_list():
    rid = _rid_from_request()
    q = Reservation.query.filter_by(restaurant_id=rid)

    # filtri
    date_s = (request.args.get("date") or "").strip()
    if date_s:
        q = q.filter(Reservation.date == date_s)

    last_days = request.args.get("last_days", type=int)
    if last_days:
        start = (datetime.now().date() - timedelta(days=last_days)).isoformat()
        q = q.filter(Reservation.date >= start)

    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        q = q.filter(
            (Reservation.customer_name.ilike(like)) | (Reservation.customer_phone.ilike(like)) | (Reservation.time.ilike(like))
        )

    items = (
        q.order_by(Reservation.date.asc(), Reservation.time.asc())
        .limit(1000)
        .all()
    )

    out = [
        {
            "id": r.id,
            "date": r.date,
            "time": r.time,
            "name": r.customer_name,
            "phone": r.customer_phone,
            "party_size": r.party_size,
            "status": r.status,
            "notes": r.notes or "",
        }
        for r in items
    ]
    return jsonify({"ok": True, "items": out})


@api_admin.post("/reservations/create")
@login_required
def reservations_create():
    rid = _rid_from_request()
    data = request.get_json(force=True, silent=True) or {}

    required = ["date", "time", "name", "party_size"]
    missing = [k for k in required if (data.get(k) is None or str(data.get(k)).strip() == "")]
    if missing:
        return jsonify({"ok": False, "error": "missing_fields", "fields": missing}), 400

    if not _is_iso_date(data["date"]) or not _is_hhmm(data["time"]):
        return jsonify({"ok": False, "error": "bad_datetime"}), 400

    try:
        res = Reservation(
            restaurant_id=rid,
            date=str(data["date"]),
            time=str(data["time"]),
            customer_name=str(data.get("name", "")).strip(),
            customer_phone=str(data.get("phone", "")).strip(),
            party_size=int(data.get("party_size") or 1),
            status=str(data.get("status") or "confirmed"),
            notes=(data.get("notes") or "").strip(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(res)
        db.session.commit()
        return jsonify({"ok": True, "id": res.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

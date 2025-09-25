# backend/admin_schedule.py
import os
import re
from typing import List, Tuple
from flask import Blueprint, request, jsonify, abort, render_template

from backend.models import db
from backend.rules_service import OpeningHour, SpecialDay, RestaurantSetting

# =======================
# Config / Auth
# =======================
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

# Un unico blueprint per API + pagina admin
api_admin = Blueprint("api_admin", __name__)

def _auth():
    tok = request.headers.get("X-Admin-Token") or request.args.get("token")
    if not tok or tok != ADMIN_TOKEN:
        abort(401)

# =======================
# Pagina admin (UI)
# =======================
@api_admin.get("/admin/schedule")
def admin_schedule_page():
    """
    Pagina admin minimale: espone una UI per mandare comandi alla API admin
    usando l'header X-Admin-Token. Il token LO inserisci dalla pagina,
    viene salvato nella sessione tramite i tuoi endpoint /api/public/sessions/:sid.
    """
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
WEEKMAP = {
    "mon": 0, "monday":0, "lun":0, "lunedì":0,
    "tue": 1, "martedi":1, "martedì":1, "tuesday":1,
    "wed": 2, "mercoledi":2, "mercoledì":2, "wednesday":2,
    "thu": 3, "giovedi":3, "giovedì":3, "thursday":3,
    "fri": 4, "venerdi":4, "venerdì":4, "friday":4,
    "sat": 5, "sabato":5, "saturday":5,
    "sun": 6, "domenica":6, "sunday":6,
}

def parse_range_list(s: str) -> List[Tuple[str, str]]:
    """
    "12:00-15:00,19:00-23:30" -> [("12:00","15:00"),("19:00","23:30")]
    """
    out: List[Tuple[str,str]] = []
    for part in re.split(r"\s*,\s*", s.strip()):
        if not part:
            continue
        m = re.match(r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$", part)
        if not m:
            raise ValueError(f"bad range: {part}")
        out.append((m.group(1), m.group(2)))
    return out

# =======================
# JSON Admin endpoints
# =======================
@api_admin.post("/api/admin/opening-hours/bulk")
def opening_hours_bulk():
    """
    JSON:
    {
      "restaurant_id": 1,
      "weekday": "mon",      // o 0..6
      "ranges": "12:00-15:00,19:00-23:30"   // oppure ["12:00-15:00", ...]
    }
    Sostituisce completamente le fasce per quel weekday.
    """
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    wd  = data.get("weekday")
    if isinstance(wd, str):
        wd_key = wd.strip().lower()
        if wd_key not in WEEKMAP:
            return jsonify({"ok": False, "error": "bad_weekday"}), 400
        weekday = WEEKMAP[wd_key]
    else:
        weekday = int(wd)

    rngs = data.get("ranges")
    if isinstance(rngs, str):
        ranges = parse_range_list(rngs)
    else:
        ranges = []
        for s in (rngs or []):
            a,b = s.split("-",1)
            ranges.append((a.strip(), b.strip()))

    db.session.query(OpeningHour).filter_by(restaurant_id=rid, weekday=weekday).delete()
    for a,b in ranges:
        db.session.add(OpeningHour(restaurant_id=rid, weekday=weekday, start_time=a, end_time=b))
    db.session.commit()
    return jsonify({"ok": True, "weekday": weekday, "count": len(ranges)}), 200


@api_admin.post("/api/admin/special-days/upsert")
def special_days_upsert():
    """
    JSON:
    { "restaurant_id":1, "date":"2025-12-25", "closed":true }
    oppure
    { "restaurant_id":1, "date":"2025-08-15", "ranges":"18:00-23:00" }
    (se ranges è lista o stringa multipla, inserisce più righe)
    """
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    date_s = (data.get("date") or "").strip()
    closed = bool(data.get("closed"))
    ranges = data.get("ranges")

    db.session.query(SpecialDay).filter_by(restaurant_id=rid, date=date_s).delete()
    if closed:
        db.session.add(SpecialDay(restaurant_id=rid, date=date_s, is_closed=True))
    else:
        if isinstance(ranges, str):
            lst = parse_range_list(ranges)
        else:
            lst = []
            for s in (ranges or []):
                a,b = s.split("-",1)
                lst.append((a.strip(), b.strip()))
        for a,b in lst:
            db.session.add(SpecialDay(restaurant_id=rid, date=date_s, is_closed=False, start_time=a, end_time=b))
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_admin.post("/api/admin/special-days/delete")
def special_days_delete():
    """
    JSON:
    { "restaurant_id":1, "date":"2025-12-26" }
    Elimina la regola speciale per quella data (se c'è).
    """
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    date_s = (data.get("date") or "").strip()
    db.session.query(SpecialDay).filter_by(restaurant_id=rid, date=date_s).delete()
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_admin.post("/api/admin/settings/update")
def settings_update():
    """
    JSON:
    {
      "restaurant_id":1,
      "tz":"Europe/Rome",
      "slot_step_min":15,
      "last_order_min":15,
      "min_party":1,
      "max_party":12,
      "capacity_per_slot":6
    }
    Qualsiasi campo assente non viene toccato.
    """
    _auth()
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    if not rid:
        return jsonify({"ok": False, "error":"missing restaurant_id"}), 400

    s = RestaurantSetting.query.get(rid) or RestaurantSetting(restaurant_id=rid)
    for k in ["tz","slot_step_min","last_order_min","min_party","max_party","capacity_per_slot"]:
        if k in data and data[k] is not None:
            setattr(s, k, data[k])
    db.session.add(s)
    db.session.commit()
    return jsonify({"ok": True}), 200


# =======================
# Endpoint COMANDI testuali
# =======================
@api_admin.post("/api/admin/schedule/commands")
def schedule_commands():
    """
    Content-Type: text/plain oppure JSON {"commands":"..."}.
    Sintassi (case-insensitive, spazi liberi):

      RID=1
      WEEK mon 12:00-15:00,19:00-23:30
      WEEK tue CLOSED
      WEEK sun 12:00-15:00
      SPECIAL 2025-12-25 CLOSED
      SPECIAL 2025-08-15 18:00-23:00
      SETTINGS step=15 last=15 capacity=6 party=1-12 tz=Europe/Rome

    Esegue in transazione unica.
    """
    _auth()
    if request.is_json:
        data = request.get_json() or {}
        text = (data.get("commands") or "").strip()
    else:
        text = (request.get_data(as_text=True) or "").strip()

    rid = None
    ops = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        u = line.lower()

        # RID=1
        m = re.match(r"^rid\s*=\s*(\d+)$", u)
        if m:
            rid = int(m.group(1))
            continue

        # WEEK <weekday> <ranges|CLOSED>
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

        # SPECIAL <YYYY-MM-DD> CLOSED | <ranges>
        m = re.match(r"^special\s+(\d{4}-\d{2}-\d{2})\s+(.+)$", u)
        if m:
            date_s = m.group(1)
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

        # SETTINGS step=15 last=15 capacity=6 party=1-12 tz=Europe/Rome
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
                    for a,b in rngs:
                        db.session.add(OpeningHour(restaurant_id=rid, weekday=weekday, start_time=a, end_time=b))

                elif op[0] == "SPECIAL_REPLACE":
                    date_s, mode, rngs = op[1], op[2], op[3]
                    db.session.query(SpecialDay).filter_by(restaurant_id=rid, date=date_s).delete()
                    if mode == "closed":
                        db.session.add(SpecialDay(restaurant_id=rid, date=date_s, is_closed=True))
                    else:
                        for a,b in rngs:
                            db.session.add(SpecialDay(
                                restaurant_id=rid, date=date_s, is_closed=False,
                                start_time=a, end_time=b
                            ))

                elif op[0] == "SETTINGS":
                    args = op[1]
                    s = RestaurantSetting.query.get(rid) or RestaurantSetting(restaurant_id=rid)
                    if "step" in args: s.slot_step_min = int(args["step"])
                    if "last" in args: s.last_order_min = int(args["last"])
                    if "capacity" in args: s.capacity_per_slot = int(args["capacity"])
                    if "tz" in args: s.tz = args["tz"]
                    if "party" in args:
                        m = re.match(r"^(\d+)-(\d+)$", args["party"])
                        if m:
                            s.min_party = int(m.group(1))
                            s.max_party = int(m.group(2))
                    db.session.add(s)

        return jsonify({"ok": True, "restaurant_id": rid, "ops": len(ops)}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

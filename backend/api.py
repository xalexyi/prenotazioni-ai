from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import or_
from flask_login import current_user, login_required
from datetime import datetime, timedelta
import re

from .models import (
    db,
    Reservation,
    ReservationPizza,
    Pizza,
    Restaurant,
    InboundNumber,
    CallLog,
)

# === per gestione orari/impostazioni ===
from backend.rules_service import OpeningHour, SpecialDay, RestaurantSetting

api = Blueprint("api", __name__, url_prefix="/api")

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def current_restaurant() -> Restaurant | None:
    """Ritorna il ristorante corrente (da flask-login o da sessione)."""
    rid = getattr(current_user, "restaurant_id", None) or session.get("restaurant_id")
    return Restaurant.query.get(rid) if rid else None


def _ensure_restaurant_id():
    r = current_restaurant()
    if not r:
        return None, (jsonify({"ok": False, "error": "not_authenticated"}), 401)
    return r.id, None


_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _is_hhmm(s: str) -> bool:
    return bool(_TIME_RE.match(s or ""))

# -------------------------------------------------------------------
# MENU PIZZERIA
# -------------------------------------------------------------------
@api.get("/menu")
@login_required
def get_menu():
    r = current_restaurant()
    if not r:
        return jsonify([])
    items = Pizza.query.filter_by(restaurant_id=r.id).order_by(Pizza.name.asc()).all()
    return jsonify([{"id": p.id, "name": p.name, "price": p.price} for p in items])

# -------------------------------------------------------------------
# LISTA PRENOTAZIONI
# -------------------------------------------------------------------
@api.get("/reservations")
@login_required
def list_reservations():
    r = current_restaurant()
    if not r:
        return jsonify([])

    q = Reservation.query.filter_by(restaurant_id=r.id)

    rng = request.args.get("range")
    date_s = request.args.get("date")
    text = request.args.get("q")

    if date_s:
        q = q.filter(Reservation.date == date_s)
    if text:
        like = f"%{text}%"
        q = q.filter(
            or_(
                Reservation.customer_name.ilike(like),
                Reservation.phone.ilike(like),
                Reservation.time.ilike(like),
            )
        )
    if rng == "today":
        from datetime import date as d
        q = q.filter(Reservation.date == d.today().isoformat())

    if rng == "30days":
        # Nota: limita a 30 prenotazioni più recenti, non 30 giorni
        q = q.order_by(Reservation.created_at.desc()).limit(30)

    q = q.order_by(Reservation.date.asc(), Reservation.time.asc(), Reservation.id.asc())
    reservations = q.all()

    out = []
    for res in reservations:
        pizzas = [
            {"id": rp.pizza_id, "name": rp.pizza.name, "qty": rp.quantity}
            for rp in res.pizzas
        ]
        out.append(
            {
                "id": res.id,
                "customer_name": res.customer_name,
                "phone": res.phone,
                "date": res.date,
                "time": res.time,
                "people": res.people,
                "status": res.status,
                "pizzas": pizzas,
            }
        )
    return jsonify(out)

# -------------------------------------------------------------------
# CREA PRENOTAZIONE (login)
# -------------------------------------------------------------------
@api.post("/reservations")
@login_required
def create_reservation():
    r = current_restaurant()
    data = request.get_json(force=True) or {}
    try:
        res = Reservation(
            restaurant_id=r.id,
            customer_name=data["customer_name"],
            phone=data["phone"],
            date=data["date"],
            time=data["time"],
            people=int(data.get("people", 2)),
            status="pending",
        )
    except KeyError as e:
        return jsonify({"ok": False, "error": "missing_field", "field": str(e)}), 400

    db.session.add(res)
    db.session.flush()

    pizzas = data.get("pizzas", [])
    for item in pizzas:
        pid = int(item.get("pizza_id", 0) or 0)
        qty = int(item.get("qty", 0) or 0)
        if pid and qty > 0:
            db.session.add(
                ReservationPizza(reservation_id=res.id, pizza_id=pid, quantity=qty)
            )

    db.session.commit()
    return jsonify({"ok": True, "id": res.id})

# -------------------------------------------------------------------
# CREA PRENOTAZIONE PUBBLICA (per n8n)
# -------------------------------------------------------------------
@api.post("/public/reservations")
def public_create_reservation():
    """
    Endpoint usato da n8n (senza login) per inserire prenotazioni.
    Richiede: customer_name, phone, date, time, people, restaurant_id
    """
    data = request.get_json(force=True) or {}

    required = ["customer_name", "phone", "date", "time", "people", "restaurant_id"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"ok": False, "error": "missing_fields", "fields": missing}), 400

    try:
        res = Reservation(
            restaurant_id=int(data["restaurant_id"]),
            customer_name=data["customer_name"],
            phone=data["phone"],
            date=data["date"],
            time=data["time"],
            people=int(data["people"]),
            status="pending",
        )
    except Exception as e:
        return jsonify({"ok": False, "error": "invalid_payload", "detail": str(e)}), 400

    db.session.add(res)
    db.session.commit()
    return jsonify({"ok": True, "id": res.id}), 201

# -------------------------------------------------------------------
# UPDATE STATO
# -------------------------------------------------------------------
@api.patch("/reservations/<int:rid>")
@login_required
def update_reservation(rid):
    r = current_restaurant()
    res = Reservation.query.filter_by(id=rid, restaurant_id=r.id).first_or_404()
    data = request.get_json(force=True) or {}
    status = data.get("status")
    if status in ("pending", "confirmed", "rejected"):
        res.status = status
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "invalid_status"}), 400

# -------------------------------------------------------------------
# DELETE
# -------------------------------------------------------------------
@api.delete("/reservations/<int:rid>")
@login_required
def delete_reservation(rid):
    r = current_restaurant()
    res = Reservation.query.filter_by(id=rid, restaurant_id=r.id).first_or_404()
    db.session.delete(res)
    db.session.commit()
    return ("", 204)

# -------------------------------------------------------------------
# N8N / TWILIO CALLS WEBHOOK (registrazione chiamate)
# -------------------------------------------------------------------
@api.post("/calls")
def api_calls():
    data = request.get_json(force=True) or {}

    expected = [
        "call_sid",
        "from",
        "to",
        "recording_sid",
        "recording_url",
        "duration_seconds",
        "transcript",
        "received_at",
    ]
    missing = [k for k in expected if k not in data]
    if missing:
        return jsonify({"ok": False, "error": "missing_fields", "fields": missing}), 400

    ib = InboundNumber.query.filter_by(e164_number=data["to"]).first()
    restaurant_id = ib.restaurant_id if ib else None

    try:
        duration = int(data.get("duration_seconds") or 0)
    except Exception:
        duration = 0

    try:
        received_at = datetime.fromisoformat(str(data["received_at"]).replace("Z", "+00:00"))
    except Exception:
        received_at = datetime.utcnow()

    log = CallLog(
        restaurant_id=restaurant_id,
        call_sid=data["call_sid"],
        from_number=data["from"],
        to_number=data["to"],
        recording_sid=data["recording_sid"],
        recording_url=data["recording_url"],
        duration_seconds=duration,
        transcript=data.get("transcript", ""),
        received_at=received_at,
    )

    db.session.add(log)
    db.session.commit()

    return jsonify({"ok": True, "id": log.id}), 200

# -------------------------------------------------------------------
# SESSIONS (per n8n)
# -------------------------------------------------------------------
@api.get("/sessions/<sid>")
def get_session(sid):
    store = current_app.config.setdefault("_sessions", {})
    return jsonify(store.get(sid, {}))


@api.patch("/sessions/<sid>")
def patch_session(sid):
    store = current_app.config.setdefault("_sessions", {})
    data = request.get_json(force=True) or {}

    update = data.get("update")
    if update is None and "session" in data:
        update = {"session": data.get("session")}
    if update is None:
        update = {}

    restaurant_id = data.get("restaurant_id")
    if restaurant_id:
        update["restaurant_id"] = restaurant_id

    # opzionale: accettiamo anche un flag "active" true/false per il badge
    if "active" in data:
        update["active"] = bool(data["active"])

    store[sid] = {**store.get(sid, {}), **update}
    return jsonify({"ok": True, "session": store[sid]})


@api.post("/sessions/<sid>")
def post_session(sid):
    return patch_session(sid)


@api.delete("/sessions/<sid>")
def delete_session(sid):
    store = current_app.config.setdefault("_sessions", {})
    if sid in store:
        del store[sid]
        return jsonify({"ok": True, "deleted": sid})
    else:
        return jsonify({"ok": False, "error": "not_found"}), 404

# -------------------------------------------------------------------
# PUBLIC ALIASES
# -------------------------------------------------------------------
@api.get("/public/sessions/<sid>")
def public_get_session(sid):
    return get_session(sid)


@api.patch("/public/sessions/<sid>")
def public_patch_session(sid):
    return patch_session(sid)


@api.post("/public/sessions/<sid>")
def public_post_session(sid):
    return post_session(sid)


@api.delete("/public/sessions/<sid>")
def public_delete_session(sid):
    return delete_session(sid)

# -------------------------------------------------------------------
# RESTAURANT LOOKUP PER NUMERO
# -------------------------------------------------------------------
@api.get("/public/restaurants/byNumber")
def public_restaurant_by_number():
    to = request.args.get("to")
    if not to:
        return jsonify({"error": "missing 'to'"}), 400

    ino = InboundNumber.query.filter_by(e164_number=to, active=True).first()
    if not ino:
        return jsonify({"error": "not_found"}), 404

    r = Restaurant.query.get(ino.restaurant_id)
    if not r:
        return jsonify({"error": "not_found"}), 404

    return jsonify({"id": r.id, "name": r.name})

# -------------------------------------------------------------------
# VOICE BADGE: stato linee attive
# -------------------------------------------------------------------
def _voice_max_lines(rid: int) -> int:
    """
    Numero massimo linee contemporanee.
    - Legge da config VOICE_MAX (intero) se presente
    - altrimenti default = 3
    """
    try:
        return int(current_app.config.get("VOICE_MAX", 3))
    except Exception:
        return 3


def _count_active_calls(rid: int) -> int:
    """
    Conteggio 'attivi' stimato:
    - Conta le sessioni in-memory (`/sessions/<sid>`) che hanno restaurant_id = rid.
      n8n crea/aggiorna queste sessioni durante la chiamata e le cancella a fine chiamata.
    - Fallback: conta CallSession con step != 'done' nelle ultime 2 ore.
    """
    # 1) In-memory sessions (usate dal tuo /sessions/<sid>)
    store = current_app.config.setdefault("_sessions", {})
    active = 0
    for sid, sess in store.items():
        try:
            if int(sess.get("restaurant_id") or 0) == int(rid):
                if "active" in sess:
                    if bool(sess["active"]):
                        active += 1
                else:
                    active += 1
        except Exception:
            continue

    # 2) Fallback DB: CallSession non conclusi (nelle ultime 2 ore)
    try:
        from .models import CallSession  # import lazy per evitare cicli
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        active_db = (
            CallSession.query
            .filter(CallSession.restaurant_id == rid)
            .filter(CallSession.step != "done")
            .filter(CallSession.created_at >= two_hours_ago)
            .count()
        )
        active = max(active, active_db)
    except Exception:
        pass

    return active


@api.get("/public/voice/active/<int:rid>")
def public_voice_active(rid):
    """
    Restituisce lo stato per il badge 'Chiamate attive':
    {
      "ok": true,
      "active": 1,
      "max": 3,
      "overload": false
    }
    """
    max_lines = _voice_max_lines(rid)
    active = _count_active_calls(rid)
    return jsonify({"ok": True, "active": int(active), "max": int(max_lines), "overload": active >= max_lines})

# ===================================================================
#  ADMIN SCOPED (CLIENTE LOGGATO) — ORARI / SPECIAL / SETTINGS
# ===================================================================
def _load_weekly_as_list(rid: int):
    """
    Restituisce:
    [
      {"weekday":0, "ranges":[{"start":"12:00","end":"15:00"}, ...]},
      ...
    ]
    """
    rows = (
        OpeningHour.query.filter_by(restaurant_id=rid)
        .order_by(OpeningHour.weekday.asc(), OpeningHour.start_time.asc())
        .all()
    )
    tmp = {i: [] for i in range(7)}
    for h in rows:
        tmp[h.weekday].append({"start": h.start_time, "end": h.end_time})
    return [{"weekday": i, "ranges": tmp[i]} for i in range(7)]


def _load_settings(rid: int):
    s = RestaurantSetting.query.filter_by(restaurant_id=rid).first()
    if not s:
        return {
            "tz": "Europe/Rome",
            "slot_step_min": 15,
            "last_order_min": 15,
            "min_party": 1,
            "max_party": 12,
            "capacity_per_slot": 6,
        }
    return {
        "tz": s.tz,
        "slot_step_min": s.slot_step_min,
        "last_order_min": s.last_order_min,
        "min_party": s.min_party,
        "max_party": s.max_party,
        "capacity_per_slot": s.capacity_per_slot,
    }


@api.get("/admin/schedule/state")
@login_required
def admin_schedule_state():
    rid, err = _ensure_restaurant_id()
    if err:
        return err

    weekly = _load_weekly_as_list(rid)

    specials = (
        SpecialDay.query.filter_by(restaurant_id=rid)
        .order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc())
        .all()
    )
    sp = {}
    for s in specials:
        day = sp.setdefault(s.date, {"date": s.date, "closed": False, "ranges": []})
        if s.is_closed:
            day["closed"] = True
        elif s.start_time and s.end_time:
            day["ranges"].append({"start": s.start_time, "end": s.end_time})

    settings = _load_settings(rid)
    return jsonify(
        {
            "ok": True,
            "weekly": weekly,
            "special_days": list(sp.values()),
            "settings": settings,
        }
    )


@api.post("/admin/schedule/weekly")
@login_required
def admin_schedule_weekly():
    """
    JSON:
    {
      "weekly": [
        {"weekday":0, "ranges":[{"start":"12:00","end":"15:00"},{"start":"19:00","end":"23:30"}]},
        ...
      ]
    }
    (replace completo)
    """
    rid, err = _ensure_restaurant_id()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    weekly = data.get("weekly") or []

    # Validazione base
    for d in weekly:
        if "weekday" not in d:
            return jsonify({"ok": False, "error": "missing weekday"}), 400
        wd = int(d.get("weekday"))
        if wd < 0 or wd > 6:
            return jsonify({"ok": False, "error": "invalid weekday"}), 400
        for rge in d.get("ranges") or []:
            a = (rge.get("start") or "").strip()
            b = (rge.get("end") or "").strip()
            if not (_is_hhmm(a) and _is_hhmm(b)):
                return jsonify({"ok": False, "error": "invalid_time_format", "hint": "use HH:MM"}), 400

    try:
        with db.session.begin():
            # Cancella e riscrive per ciascun giorno
            for d in weekly:
                wd = int(d.get("weekday"))
                rngs = d.get("ranges") or []
                db.session.query(OpeningHour).filter_by(restaurant_id=rid, weekday=wd).delete()
                for rge in rngs:
                    a = (rge.get("start") or "").strip()
                    b = (rge.get("end") or "").strip()
                    if a and b:
                        db.session.add(
                            OpeningHour(
                                restaurant_id=rid,
                                weekday=wd,
                                start_time=a,
                                end_time=b,
                            )
                        )
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 400


@api.post("/admin/schedule/settings")
@login_required
def admin_schedule_settings():
    """
    JSON (tutti opzionali):
    {
      "tz":"Europe/Rome",
      "slot_step_min":15,
      "last_order_min":15,
      "min_party":1,
      "max_party":12,
      "capacity_per_slot":6
    }
    """
    rid, err = _ensure_restaurant_id()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}

    s = RestaurantSetting.query.filter_by(restaurant_id=rid).first()
    if not s:
        s = RestaurantSetting(restaurant_id=rid)

    for k in ["tz", "slot_step_min", "last_order_min", "min_party", "max_party", "capacity_per_slot"]:
        if k in data and data[k] is not None:
            setattr(s, k, data[k])

    db.session.add(s)
    db.session.commit()
    return jsonify({"ok": True, "settings": _load_settings(rid)})


@api.get("/admin/special-days/list")
@login_required
def admin_special_days_list():
    rid, err = _ensure_restaurant_id()
    if err:
        return err
    q = SpecialDay.query.filter_by(restaurant_id=rid)
    _from = request.args.get("from")
    _to = request.args.get("to")
    if _from:
        q = q.filter(SpecialDay.date >= _from)
    if _to:
        q = q.filter(SpecialDay.date <= _to)

    rows = q.order_by(SpecialDay.date.asc(), SpecialDay.start_time.asc()).all()
    out = {}
    for s in rows:
        day = out.setdefault(s.date, {"date": s.date, "closed": False, "ranges": []})
        if s.is_closed:
            day["closed"] = True
        elif s.start_time and s.end_time:
            day["ranges"].append({"start": s.start_time, "end": s.end_time})
    return jsonify({"ok": True, "items": list(out.values())})


@api.post("/admin/special-days/upsert")
@login_required
def admin_special_days_upsert():
    """
    JSON:
    { "date":"2025-12-25", "closed":true }
    oppure
    { "date":"2025-08-15", "ranges":[{"start":"18:00","end":"23:00"}] }
    """
    rid, err = _ensure_restaurant_id()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    date_s = (data.get("date") or "").strip()
    closed = bool(data.get("closed"))
    ranges = data.get("ranges") or []

    if not date_s:
        return jsonify({"ok": False, "error": "missing date"}), 400

    # Validazione orari
    for rge in ranges:
        a = (rge.get("start") or "").strip()
        b = (rge.get("end") or "").strip()
        if not (_is_hhmm(a) and _is_hhmm(b)):
            return jsonify({"ok": False, "error": "invalid_time_format", "hint": "use HH:MM"}), 400

    try:
        with db.session.begin():
            db.session.query(SpecialDay).filter_by(restaurant_id=rid, date=date_s).delete()
            if closed:
                db.session.add(SpecialDay(restaurant_id=rid, date=date_s, is_closed=True))
            else:
                for rge in ranges:
                    a = (rge.get("start") or "").strip()
                    b = (rge.get("end") or "").strip()
                    if a and b:
                        db.session.add(
                            SpecialDay(
                                restaurant_id=rid,
                                date=date_s,
                                is_closed=False,
                                start_time=a,
                                end_time=b,
                            )
                        )
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 400


@api.post("/admin/special-days/delete")
@login_required
def admin_special_days_delete():
    rid, err = _ensure_restaurant_id()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    date_s = (data.get("date") or "").strip()
    if not date_s:
        return jsonify({"ok": False, "error": "missing date"}), 400
    db.session.query(SpecialDay).filter_by(restaurant_id=rid, date=date_s).delete()
    db.session.commit()
    return jsonify({"ok": True})

from flask import Blueprint, request, jsonify, session, abort
from sqlalchemy import or_
from flask_login import current_user, login_required
from datetime import datetime

from .models import (
    db,
    Reservation,
    ReservationPizza,
    Pizza,
    Restaurant,
    InboundNumber,
    CallLog,
)

api = Blueprint("api", __name__, url_prefix="/api")


def current_restaurant() -> Restaurant:
    """Ritorna il ristorante corrente (da flask-login o da sessione)."""
    rid = getattr(current_user, "restaurant_id", None) or session.get("restaurant_id")
    return Restaurant.query.get(rid)


# -------------------- MENU PIZZERIA --------------------
@api.get("/menu")
@login_required
def get_menu():
    r = current_restaurant()
    if not r:
        return jsonify([])

    items = Pizza.query.filter_by(restaurant_id=r.id).order_by(Pizza.name.asc()).all()
    return jsonify([{"id": p.id, "name": p.name, "price": p.price} for p in items])


# -------------------- LISTA PRENOTAZIONI --------------------
@api.get("/reservations")
@login_required
def list_reservations():
    r = current_restaurant()
    if not r:
        return jsonify([])

    q = Reservation.query.filter_by(restaurant_id=r.id)

    rng = request.args.get("range")
    date = request.args.get("date")
    text = request.args.get("q")

    if date:
        q = q.filter(Reservation.date == date)
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


# -------------------- CREA PRENOTAZIONE (login) --------------------
@api.post("/reservations")
@login_required
def create_reservation():
    r = current_restaurant()
    data = request.get_json(force=True) or {}
    res = Reservation(
        restaurant_id=r.id,
        customer_name=data["customer_name"],
        phone=data["phone"],
        date=data["date"],
        time=data["time"],
        people=int(data.get("people", 2)),
        status="pending",
    )
    db.session.add(res)
    db.session.flush()

    pizzas = data.get("pizzas", [])
    for item in pizzas:
        pid = int(item.get("pizza_id"))
        qty = int(item.get("qty", 1))
        if pid and qty > 0:
            db.session.add(
                ReservationPizza(reservation_id=res.id, pizza_id=pid, quantity=qty)
            )

    db.session.commit()
    return jsonify({"ok": True, "id": res.id})


# -------------------- CREA PRENOTAZIONE PUBBLICA (per n8n) --------------------
@api.post("/public/reservations")
def public_create_reservation():
    """
    Endpoint usato da n8n (senza login) per inserire prenotazioni.
    Richiede almeno: customer_name, phone, date, time, people, restaurant_id
    """
    data = request.get_json(force=True) or {}

    required = ["customer_name", "phone", "date", "time", "people", "restaurant_id"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"ok": False, "error": "missing_fields", "fields": missing}), 400

    res = Reservation(
        restaurant_id=int(data["restaurant_id"]),
        customer_name=data["customer_name"],
        phone=data["phone"],
        date=data["date"],
        time=data["time"],
        people=int(data["people"]),
        status="pending",
    )
    db.session.add(res)
    db.session.commit()

    return jsonify({"ok": True, "id": res.id}), 201


# -------------------- UPDATE STATO --------------------
@api.patch("/reservations/<int:rid>")
@login_required
def update_reservation(rid):
    r = current_restaurant()
    res = Reservation.query.filter_by(id=rid, restaurant_id=r.id).first_or_404()
    data = request.get_json(force=True)
    status = data.get("status")
    if status in ("pending", "confirmed", "rejected"):
        res.status = status
        db.session.commit()
    return jsonify({"ok": True})


# -------------------- DELETE --------------------
@api.delete("/reservations/<int:rid>")
@login_required
def delete_reservation(rid):
    r = current_restaurant()
    res = Reservation.query.filter_by(id=rid, restaurant_id=r.id).first_or_404()
    db.session.delete(res)
    db.session.commit()
    return ("", 204)


# ==================== SESSIONS (per n8n) ====================
@api.get("/sessions/<sid>")
def get_session(sid):
    from flask import current_app
    store = current_app.config.setdefault("_sessions", {})
    return jsonify(store.get(sid, {}))


@api.patch("/sessions/<sid>")
def patch_session(sid):
    from flask import current_app
    store = current_app.config.setdefault("_sessions", {})
    data = request.get_json(force=True) or {}
    update = data.get("update", {})
    if sid not in store:
        store[sid] = {}
    store[sid].update(update)
    return jsonify({"ok": True, "session": store[sid]})


@api.delete("/sessions/<sid>")
def delete_session(sid):
    from flask import current_app
    store = current_app.config.setdefault("_sessions", {})
    if sid in store:
        store.pop(sid)
        return jsonify({"ok": True, "deleted": sid}), 200
    return jsonify({"ok": False, "error": "not_found"}), 404


# ==================== N8N / TWILIO CALLS WEBHOOK ====================
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
        received_at = datetime.fromisoformat(data["received_at"].replace("Z", "+00:00"))
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

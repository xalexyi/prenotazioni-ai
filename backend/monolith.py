"""
Helper riusabili per il backend (no side-effect all'import).
Queste funzioni sono facoltative: puoi importarle dove servono.
Sono scritte per evitare import circolari (import locali dentro le funzioni).
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

from sqlalchemy import func

# NB: non importiamo app/db a livello modulo per evitare loop.


# ---------------------------- SETTINGS / PRICING ---------------------------- #

def require_settings_for_restaurant(rest_id: int):
    """Ritorna/imposta le Settings del ristorante in modo idempotente."""
    from app import db
    from backend.models import Settings
    s = Settings.query.filter_by(restaurant_id=rest_id).first()
    if not s:
        s = Settings(
            restaurant_id=rest_id,
            avg_price=25.0,
            cover=0.0,
            seats_cap=None,
            min_people=None,
            menu_url=None,
            menu_desc=None,
        )
        db.session.add(s)
        db.session.commit()
    return s


def upsert_pricing(rest_id: int, data: Dict[str, Any]) -> None:
    """Aggiorna i prezzi base (avg_price, cover, seats_cap, min_people)."""
    from app import db
    s = require_settings_for_restaurant(rest_id)
    if "avg_price" in data and data["avg_price"] != "":
        s.avg_price = float(data["avg_price"])
    if "cover" in data and data["cover"] != "":
        s.cover = float(data["cover"])
    if "seats_cap" in data and data["seats_cap"] != "":
        s.seats_cap = int(data["seats_cap"])
    if "min_people" in data and data["min_people"] != "":
        s.min_people = int(data["min_people"])
    db.session.commit()


# ----------------------- ORARI SETTIMANALI / SPECIALI ---------------------- #

def upsert_opening_hours(rest_id: int, hours_map: Dict[str, str]) -> None:
    """
    hours_map: { "0": "12:00-15:00, 19:00-22:30", ..., "6": "" }
    Scrive in tabella opening_hours (day_of_week INT, windows TEXT).
    """
    from app import db
    from backend.models import OpeningHours
    for d in range(7):
        win = hours_map.get(str(d), "")
        row = OpeningHours.query.filter_by(restaurant_id=rest_id, day_of_week=d).first()
        if not row:
            row = OpeningHours(restaurant_id=rest_id, day_of_week=d, windows=win)
            db.session.add(row)
        else:
            row.windows = win
    db.session.commit()


def upsert_special_day(rest_id: int, day: str, closed: bool, windows: str) -> None:
    """Giorni speciali: (date TEXT 'YYYY-MM-DD', closed BOOL, windows TEXT)."""
    from app import db
    from backend.models import SpecialDay
    row = SpecialDay.query.filter_by(restaurant_id=rest_id, date=day).first()
    if not row:
        row = SpecialDay(restaurant_id=rest_id, date=day, closed=closed, windows=windows or "")
        db.session.add(row)
    else:
        row.closed = bool(closed)
        row.windows = windows or ""
    db.session.commit()


# ----------------------------- PRENOTAZIONI -------------------------------- #

def list_reservations(rest_id: int, day: Optional[str] = None, q: str = "") -> List[Dict[str, Any]]:
    """Ritorna prenotazioni (filtrate per giorno e ricerca fulltext semplice)."""
    from backend.models import Reservation
    items_q = Reservation.query.filter_by(restaurant_id=rest_id)
    if day:
        items_q = items_q.filter(Reservation.date == day)
    items = items_q.order_by(Reservation.date.asc(), Reservation.time.asc()).all()
    out: List[Dict[str, Any]] = []
    ql = (q or "").lower().strip()
    for r in items:
        if ql:
            blob = f"{r.name} {r.phone} {r.time} {r.status} {r.note or ''}".lower()
            if ql not in blob:
                continue
        out.append({
            "id": r.id,
            "date": r.date,
            "time": r.time,
            "name": r.name,
            "phone": r.phone,
            "people": r.people,
            "status": r.status,
            "note": r.note,
        })
    return out


def create_reservation(rest_id: int, payload: Dict[str, Any]) -> int:
    """Crea una prenotazione e ritorna l'ID."""
    from app import db
    from backend.models import Reservation
    r = Reservation(
        restaurant_id=rest_id,
        name=payload["name"],
        phone=payload.get("phone"),
        people=int(payload.get("people") or 2),
        status=payload.get("status") or "Confermata",
        note=payload.get("note") or "",
        date=payload["date"],  # "YYYY-MM-DD"
        time=payload["time"],  # "HH:MM"
    )
    db.session.add(r)
    db.session.commit()
    return r.id


def update_reservation(rest_id: int, rid: int, payload: Dict[str, Any]) -> None:
    """Aggiorna una prenotazione esistente."""
    from app import db
    from backend.models import Reservation
    r = Reservation.query.filter_by(id=rid, restaurant_id=rest_id).first_or_404()
    for k in ["name", "phone", "status", "note"]:
        if k in payload:
            setattr(r, k, payload[k])
    if "people" in payload:
        r.people = int(payload["people"])
    if "date" in payload:
        r.date = payload["date"]
    if "time" in payload:
        r.time = payload["time"]
    db.session.commit()


def delete_reservation(rest_id: int, rid: int) -> None:
    """Elimina una prenotazione."""
    from app import db
    from backend.models import Reservation
    r = Reservation.query.filter_by(id=rid, restaurant_id=rest_id).first_or_404()
    db.session.delete(r)
    db.session.commit()


# --------------------------------- STATS ----------------------------------- #

def compute_stats(rest_id: int, day: Optional[str] = None) -> Dict[str, Any]:
    """Statistiche base per dashboard."""
    from app import db
    from backend.models import Reservation
    from .monolith import require_settings_for_restaurant  # safe self-import

    q = Reservation.query.filter_by(restaurant_id=rest_id)
    if day:
        q = q.filter(Reservation.date == day)
    total = q.count()
    avg_people = (db.session.query(func.avg(Reservation.people))
                  .filter_by(restaurant_id=rest_id).scalar()) or 0.0

    s = require_settings_for_restaurant(rest_id)
    estimated_revenue = float(s.avg_price or 0.0) * float(total)

    return {
        "total_reservations": int(total),
        "avg_people": float(avg_people),
        "avg_price": float(s.avg_price or 0.0),
        "estimated_revenue": float(estimated_revenue),
    }

# -*- coding: utf-8 -*-
# backend/rules_service.py
#
# Re-export dei modelli dal modulo centrale (niente duplicazioni di tabelle)
# + funzioni helper usate da backend.ai: rules_from_db, validate_reservation_basic

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

from backend.models import (
    db,
    OpeningHour,
    SpecialDay,
    RestaurantSetting,
    Reservation,
    ReservationPizza,
    Pizza,
    Restaurant,
)

__all__ = [
    "db",
    # modelli
    "OpeningHour",
    "SpecialDay",
    "RestaurantSetting",
    "Reservation",
    "ReservationPizza",
    "Pizza",
    "Restaurant",
    # helpers
    "rules_from_db",
    "validate_reservation_basic",
]

# ----------------- util -----------------
def _hhmm_ok(s: str) -> bool:
    try:
        h, m = s.split(":")
        h = int(h); m = int(m)
        return 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        return False

def _to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)

def _fmt_hhmm(s: Any) -> str:
    # accetta già "HH:MM" o oggetti time
    if hasattr(s, "strftime"):
        return s.strftime("%H:%M")
    s = str(s)
    if _hhmm_ok(s):
        h, m = s.split(":")
        return f"{int(h):02d}:{int(m):02d}"
    raise ValueError("bad HH:MM")

# ----------------- API helpers -----------------
def rules_from_db(restaurant_id: int) -> Dict[str, Any]:
    """
    Ritorna la struttura regole come attesa dal resto del backend:
    {
      "weekly": [ [ {"start":"12:00","end":"15:00"}, ... ], ... (len=7) ],
      "special_days": { "YYYY-MM-DD": {"closed":bool, "ranges":[{"start","end"}]} },
      "settings": {...}
    }
    """
    weekly: List[List[Dict[str, str]]] = [[] for _ in range(7)]
    for oh in (
        OpeningHour.query.filter_by(restaurant_id=restaurant_id)
        .order_by(OpeningHour.weekday.asc(), OpeningHour.start_time.asc())
        .all()
    ):
        weekly[int(oh.weekday)].append({
            "start": _fmt_hhmm(oh.start_time),
            "end": _fmt_hhmm(oh.end_time),
        })

    specials: Dict[str, Dict[str, Any]] = {}
    for sd in (
        SpecialDay.query.filter_by(restaurant_id=restaurant_id)
        .order_by(SpecialDay.date.asc())
        .all()
    ):
        d = sd.date if isinstance(sd.date, str) else str(sd.date)
        entry = specials.setdefault(d, {"closed": False, "ranges": []})
        if sd.is_closed:
            entry["closed"] = True
            entry["ranges"] = []
        else:
            entry["ranges"].append({
                "start": _fmt_hhmm(sd.start_time),
                "end": _fmt_hhmm(sd.end_time),
            })

    s = RestaurantSetting.query.filter_by(restaurant_id=restaurant_id).first()
    settings = {
        "tz": s.tz if s else "Europe/Rome",
        "slot_step_min": s.slot_step_min if s else 15,
        "last_order_min": s.last_order_min if s else 15,
        "min_party": s.min_party if s else 1,
        "max_party": s.max_party if s else 12,
        "capacity_per_slot": s.capacity_per_slot if s else 6,
    }

    return {"weekly": weekly, "special_days": specials, "settings": settings}


def validate_reservation_basic(
    rules: Dict[str, Any],
    date_str: str,
    time_str: str,
    party_size: int,
) -> Tuple[bool, str | None]:
    """
    Controlli minimi:
    - formato data/ora
    - numero persone entro min/max
    - esistenza di almeno una fascia valida nel giorno (special ha priorità)
    - rispetto di last_order_min (prenotazione entro 'end - last_order_min')
    Ritorna (ok, error_code or None)
    """
    # formato
    try:
        the_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return False, "bad_date"

    if not _hhmm_ok(time_str):
        return False, "bad_time"

    # persone
    settings = rules.get("settings") or {}
    min_p = int(settings.get("min_party", 1) or 1)
    max_p = int(settings.get("max_party", 12) or 12)
    if party_size < min_p or party_size > max_p:
        return False, "party_out_of_range"

    # fasce disponibili (special -> weekly)
    specials = rules.get("special_days") or {}
    weekly = rules.get("weekly") or [[] for _ in range(7)]
    ds = the_date.strftime("%Y-%m-%d")
    ranges: List[Dict[str, str]] = []

    spec = specials.get(ds)
    if spec:
        if spec.get("closed"):
            return False, "closed_special"
        ranges = spec.get("ranges") or []
    else:
        wd = the_date.weekday()  # 0=Mon..6=Sun
        ranges = weekly[wd] if 0 <= wd < len(weekly) else []

    if not ranges:
        return False, "closed_weekday"

    # controllo orario in almeno una fascia, con margine last_order_min
    last_order = int(settings.get("last_order_min", 15) or 15)
    tmin = _to_min(time_str)
    for r in ranges:
        try:
            a = _to_min(_fmt_hhmm(r["start"]))
            b = _to_min(_fmt_hhmm(r["end"])) - last_order
            if tmin >= a and tmin <= b:
                return True, None
        except Exception:
            # fascia malformata -> ignorala
            continue

    return False, "time_out_of_ranges"

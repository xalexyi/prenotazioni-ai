# -*- coding: utf-8 -*-
# backend/ai.py
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

from backend.models import db, Reservation
from backend.rules_service import rules_from_db, validate_reservation_basic

_WORD2NUM = {
    "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12,
}
_TIME_RX = re.compile(r"\b([01]?\d|2[0-3])[:.\- ]?([0-5]\d)?\b")
_DATE_ISO_RX = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_IT_RX = re.compile(r"\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{4}))?\b")
_PEOPLE_DIGIT_RX = re.compile(r"\b(?:per|x|da|siamo|in)\s*(\d{1,2})\b")
_PHONE_RX = re.compile(r"(\+?\d[\d \-]{6,}\d)")

def _coerce_int(x: Optional[str], default: int) -> int:
    try:
        return default if x is None else int(x)
    except Exception:
        return default

def parse_with_ai(text: str) -> Dict[str, Any]:
    """
    Parser semplice (no LLM): estrae date/time/people/nome/telefono.
    Ritorna: {date, time, people, customer_name, phone}
    """
    s = (text or "").strip()
    low = s.lower()

    # Persone
    people = 2
    m = _PEOPLE_DIGIT_RX.search(low)
    if m:
        people = _coerce_int(m.group(1), 2)
    else:
        for w, n in _WORD2NUM.items():
            if re.search(rf"\b{w}\b", low):
                people = n
                break

    # Nome
    name = None
    m = re.search(r"\b(mi chiamo|sono)\s+([a-zà-ù]+(?:\s+[a-zà-ù]+)?)", low, re.IGNORECASE)
    if m:
        name = m.group(2).strip().title()

    # Telefono
    phone = None
    m = _PHONE_RX.search(s)
    if m:
        phone = re.sub(r"[^\d+]", "", m.group(1))

    # Data
    date_iso = None
    if "oggi" in low:
        date_iso = "__TODAY__"
    elif "domani" in low:
        date_iso = "__TOMORROW__"
    elif "dopodomani" in low:
        date_iso = "__AFTER_TOMORROW__"
    if not date_iso:
        m = _DATE_ISO_RX.search(low)
        if m:
            date_iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if not date_iso:
        m = _DATE_IT_RX.search(low)
        if m:
            dd = int(m.group(1)); mm = int(m.group(2)); yy = int(m.group(3) or datetime.utcnow().year)
            date_iso = f"{yy:04d}-{mm:02d}-{dd:02d}"

    # Orario
    time_hhmm = None
    m = _TIME_RX.search(low)
    if m:
        hh = int(m.group(1)); mm = int(m.group(2) or "00")
        time_hhmm = f"{hh:02d}:{mm:02d}"

    return {
        "date": date_iso,
        "time": time_hhmm,
        "people": people,
        "customer_name": name,
        "phone": phone,
        "raw": s,
    }

def create_reservation_db(restaurant, parsed: Dict[str, Any]) -> int:
    """
    Crea una Reservation (status 'pending') e ritorna l'id creato.
    """
    rules = rules_from_db(restaurant.id)
    tz = ZoneInfo(rules.tz)

    today = datetime.now(tz).date()
    key = parsed.get("date")
    if key in (None, "__TODAY__"):
        d = today
    elif key == "__TOMORROW__":
        d = today + timedelta(days=1)
    elif key == "__AFTER_TOMORROW__":
        d = today + timedelta(days=2)
    else:
        d = datetime.strptime(key, "%Y-%m-%d").date()

    t_str = parsed.get("time") or "20:00"
    hh, mm = [int(x) for x in t_str.split(":")]

    people = int(parsed.get("people") or 2)

    # Validazione soft (non blocca il salvataggio)
    try:
        _ok, _reason, _sug = validate_reservation_basic(
            restaurant.id,
            datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz),
            people,
        )
    except Exception:
        pass

    res = Reservation(restaurant_id=restaurant.id)
    if hasattr(res, "customer_name"):
        res.customer_name = parsed.get("customer_name") or "Cliente"
    elif hasattr(res, "name"):
        res.name = parsed.get("customer_name") or "Cliente"

    if hasattr(res, "phone"):  res.phone  = parsed.get("phone") or ""
    if hasattr(res, "date"):   res.date   = d.strftime("%Y-%m-%d")
    if hasattr(res, "time"):   res.time   = f"{hh:02d}:{mm:02d}"
    if hasattr(res, "people"): res.people = people
    if hasattr(res, "status"): res.status = "pending"
    for attr in ("source", "channel", "origin"):
        if hasattr(res, attr):
            setattr(res, attr, "voice"); break

    db.session.add(res)
    db.session.commit()
    return int(getattr(res, "id"))

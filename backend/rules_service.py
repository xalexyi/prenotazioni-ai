# backend/rules_service.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Tuple

from backend.models import db

# ===========================
#   MODELLI DATABASE
# ===========================

class OpeningHour(db.Model):
    """
    Fasce orarie settimanali ricorrenti.
    weekday: 0=lun ... 6=dom
    start_time / end_time: 'HH:MM'
    """
    __tablename__ = "opening_hours"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False)  # 0..6
    start_time = db.Column(db.String(5), nullable=False)  # "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)    # "HH:MM"

    __table_args__ = (
        db.Index("idx_opening_weekday_rest", "restaurant_id", "weekday"),
    )


class SpecialDay(db.Model):
    """
    Eccezioni sul calendario: festività/chiusure o aperture speciali.
    - is_closed=True, nessuna fascia -> chiuso tutto il giorno
    - is_closed=False + una o più righe (stessa data) -> aperture speciali
    """
    __tablename__ = "special_days"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, nullable=False, index=True)
    date = db.Column(db.String(10), nullable=False, index=True)  # "YYYY-MM-DD"
    is_closed = db.Column(db.Boolean, nullable=False, default=False)
    start_time = db.Column(db.String(5), nullable=True)
    end_time = db.Column(db.String(5), nullable=True)

    __table_args__ = (
        db.Index("idx_special_date_rest", "restaurant_id", "date"),
    )


class RestaurantSetting(db.Model):
    """
    Impostazioni per ristorante (override dei default).
    Se un campo è NULL → usa default.
    """
    __tablename__ = "restaurant_settings"
    restaurant_id = db.Column(db.Integer, primary_key=True)
    tz = db.Column(db.String(64), nullable=True)                 # es. "Europe/Rome"
    slot_step_min = db.Column(db.Integer, nullable=True)         # 15/30...
    last_order_min = db.Column(db.Integer, nullable=True)        # min prima fine fascia
    min_party = db.Column(db.Integer, nullable=True)
    max_party = db.Column(db.Integer, nullable=True)
    capacity_per_slot = db.Column(db.Integer, nullable=True)

# ===========================
#   STRUTTURA REGOLE
# ===========================

@dataclass
class SlotRule:
    start: time
    end: time

@dataclass
class RestaurantRules:
    tz: str
    weekly: Dict[int, List[SlotRule]]        # weekday -> [fasce]
    slot_step_min: int
    last_order_min: int
    min_party: int
    max_party: int
    capacity_per_slot: int

def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(hour=int(h), minute=int(m))

def _fmt_date(dt: datetime) -> str:
    return dt.date().isoformat()

DEFAULTS = {
    "tz": "Europe/Rome",
    "slot_step_min": 15,
    "last_order_min": 15,
    "min_party": 1,
    "max_party": 12,
    "capacity_per_slot": 6,
}

# ===========================
#   CARICAMENTO DAL DB
# ===========================

def rules_from_db(restaurant_id: int) -> RestaurantRules:
    """Costruisce le regole orarie leggendo opening_hours, special_days e settings."""
    weekly: Dict[int, List[SlotRule]] = {i: [] for i in range(7)}

    rows = (
        db.session.query(OpeningHour)
        .filter_by(restaurant_id=restaurant_id)
        .order_by(OpeningHour.weekday, OpeningHour.start_time)
        .all()
    )
    for r in rows:
        weekly[r.weekday].append(SlotRule(_parse_hhmm(r.start_time), _parse_hhmm(r.end_time)))

    s = RestaurantSetting.query.get(restaurant_id)

    def val(name):
        return getattr(s, name) if s and getattr(s, name) is not None else DEFAULTS[name]

    return RestaurantRules(
        tz= (s.tz if s and s.tz else DEFAULTS["tz"]),
        weekly=weekly,
        slot_step_min=val("slot_step_min"),
        last_order_min=val("last_order_min"),
        min_party=val("min_party"),
        max_party=val("max_party"),
        capacity_per_slot=val("capacity_per_slot"),
    )

def special_for_date(restaurant_id: int, date_s: str) -> Optional[List[SlotRule] | str]:
    """
    Ritorna:
      - "closed"          se la data è marcata chiusa
      - [SlotRule...]     se ci sono aperture speciali
      - None              se non ci sono eccezioni (usa weekly)
    """
    rows = (
        db.session.query(SpecialDay)
        .filter_by(restaurant_id=restaurant_id, date=date_s)
        .order_by(SpecialDay.start_time)
        .all()
    )
    if not rows:
        return None
    if any(r.is_closed for r in rows):
        return "closed"
    slots: List[SlotRule] = []
    for r in rows:
        if r.start_time and r.end_time:
            slots.append(SlotRule(_parse_hhmm(r.start_time), _parse_hhmm(r.end_time)))
    return slots or "closed"

# ===========================
#   VALIDATORE
# ===========================

def _in_any_slot(t: time, slots: List[SlotRule], last_order_min: int) -> Tuple[bool, Optional[time]]:
    for s in slots:
        end_effective = (datetime.combine(datetime.today(), s.end) - timedelta(minutes=last_order_min)).time()
        if s.start <= t <= end_effective:
            return True, s.end
    return False, None

def validate_reservation_basic(
    restaurant_id: int, dt_local: datetime, people: int
) -> Tuple[bool, str, Optional[datetime]]:
    """
    Valida data/ora e persone secondo le regole a DB.
    Ritorna (ok, reason, suggested_dt_local)
      reason ∈ {"closed", "outside_hours", "bad_step", "party_out_of_range", "ok"}
    """
    rules = rules_from_db(restaurant_id)
    tz = ZoneInfo(rules.tz)
    dt_local = dt_local.astimezone(tz)

    date_s = _fmt_date(dt_local)

    special = special_for_date(restaurant_id, date_s)
    if special == "closed":
        return False, "closed", None

    slots_today: List[SlotRule]
    if isinstance(special, list):
        slots_today = special
    else:
        slots_today = rules.weekly.get(dt_local.weekday(), [])

    if not slots_today:
        return False, "closed", None

    ok_time, _ = _in_any_slot(dt_local.time(), slots_today, rules.last_order_min)
    if not ok_time:
        for s in slots_today:
            start_dt = datetime.combine(dt_local.date(), s.start, tzinfo=tz)
            if dt_local < start_dt:
                return False, "outside_hours", start_dt
        return False, "outside_hours", None

    if rules.slot_step_min:
        minutes = dt_local.minute
        if minutes % rules.slot_step_min != 0:
            step = rules.slot_step_min
            delta = step - (minutes % step)
            sug = dt_local + timedelta(minutes=delta)
            return False, "bad_step", sug

    if people < rules.min_party or people > rules.max_party:
        return False, "party_out_of_range", None

    return True, "ok", None

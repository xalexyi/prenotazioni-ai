# backend/booking_validator.py
from datetime import datetime, timedelta, date as date_cls
from zoneinfo import ZoneInfo

from backend.rules_service import rules_from_db, SpecialDay

def _parse_dt_local(date_str: str, time_str: str, tz_name: str | None) -> tuple[datetime, ZoneInfo]:
    # Esempio: "2025-10-02", "20:00"
    if not tz_name:
        tz_name = "Europe/Rome"
    tz = ZoneInfo(tz_name)
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    return dt, tz

def check_opening_window(restaurant_id: int, date_str: str, time_str: str, tz_name: str | None) -> tuple[bool, dict]:
    """
    Ritorna (ok, info_errore)
      ok=True  -> prenotazione consentita
      ok=False -> fuori orario / chiuso -> info_errore["code"] in {"closed","outside_hours"}
    Logica:
      - Se esiste una special_day con is_closed=True => chiuso
      - Se esiste una special_day con start/end -> usa quella finestra
      - Altrimenti usa opening_hours del weekday
      - Applica last_order_min (se presente) accorciando l'end
    """
    rules = rules_from_db(restaurant_id)
    # timezone per il ristorante (priorità: tz richiesta -> tz da settings -> 'Europe/Rome')
    tz_final = tz_name or getattr(rules, "tz", None) or "Europe/Rome"
    dt_local, tz = _parse_dt_local(date_str, time_str, tz_final)
    d = dt_local.date()
    t = dt_local.time()
    wd = dt_local.weekday()  # 0=Mon..6=Sun

    # 1) Special day?
    sd = SpecialDay.query.filter_by(restaurant_id=restaurant_id, date=d.isoformat()).first()
    if sd:
        if sd.is_closed:
            return False, {"code": "closed", "reason": "special_day_closed"}
        if sd.start_time and sd.end_time:
            # Applica last_order
            end_dt = datetime.combine(d, sd.end_time)
            lo = getattr(rules, "last_order_min", 0) or 0
            if lo:
                end_dt = end_dt - timedelta(minutes=lo)
            end_t = end_dt.time()
            ok = (sd.start_time <= t <= end_t)
            return (ok, {} if ok else {"code": "outside_hours", "reason": "special_day_window"})

    # 2) Weekly windows
    slots = rules.weekly.get(wd, [])
    lo = getattr(rules, "last_order_min", 0) or 0
    for s in slots:
        end_dt = datetime.combine(d, s.end)
        if lo:
            end_dt = end_dt - timedelta(minutes=lo)
        end_t = end_dt.time()
        if s.start <= t <= end_t:
            return True, {}

    return False, {"code": "outside_hours", "reason": "weekly_windows"}

# -*- coding: utf-8 -*-
# backend/booking_validator.py
from __future__ import annotations

from datetime import datetime, timedelta, time
from typing import Tuple, Dict, Optional, List, Union
from zoneinfo import ZoneInfo

from backend.rules_service import (
    rules_from_db,
    special_for_date,
    SlotRule,
)

# -------------------------
# Helpers
# -------------------------
def _parse_dt_local(date_str: str, time_str: str, tz_name: str | None) -> tuple[datetime, ZoneInfo]:
    """
    Costruisce un datetime timezone-aware (nel fuso del ristorante).
    """
    tz = ZoneInfo(tz_name or "Europe/Rome")
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except Exception as e:
        raise ValueError(f"invalid datetime: {date_str} {time_str} ({e})")
    return dt, tz


def _end_effective(day_dt: datetime, end_t: time, last_order_min: int) -> datetime:
    """
    Applica il margine 'last_order_min' sottraendolo dall'orario di fine slot.
    """
    eff = datetime.combine(day_dt.date(), end_t, tzinfo=day_dt.tzinfo)
    if last_order_min:
        eff -= timedelta(minutes=int(last_order_min))
    return eff


def _first_future_start(now_local: datetime, slots: List[SlotRule]) -> Optional[datetime]:
    """
    Ritorna il prossimo 'start' nel giorno corrente che è > now_local (se esiste).
    """
    for s in slots:
        start_dt = datetime.combine(now_local.date(), s.start, tzinfo=now_local.tzinfo)
        if now_local < start_dt:
            return start_dt
    return None


# -------------------------
# API principale
# -------------------------
def check_opening_window(
    restaurant_id: int,
    date_str: str,
    time_str: str,
    tz_name: Optional[str],
    *,
    people: Optional[int] = None,
) -> tuple[bool, Dict[str, Union[str, int]]]:
    """
    Verifica se una prenotazione cade entro le finestre di apertura.

    Ritorna (ok, info)
      ok=True  -> prenotazione consentita
      ok=False -> info["code"] in {"closed","outside_hours","bad_step","party_out_of_range"}
                  e può contenere "suggested": "YYYY-MM-DDTHH:MM"
    """
    rules = rules_from_db(restaurant_id)
    tz_final = tz_name or getattr(rules, "tz", None) or "Europe/Rome"
    dt_local, tz = _parse_dt_local(date_str, time_str, tz_final)

    # 1) Special day override
    special = special_for_date(restaurant_id, date_str)
    if special == "closed":
        return False, {"code": "closed", "reason": "special_day_closed"}

    if isinstance(special, list):
        slots_today = special
    else:
        # weekly fallback
        slots_today = rules.weekly.get(dt_local.weekday(), [])

    if not slots_today:
        return False, {"code": "closed", "reason": "no_weekly_slots"}

    # 2) Controllo persone (se richiesto)
    if people is not None:
        if people < rules.min_party or people > rules.max_party:
            return (
                False,
                {
                    "code": "party_out_of_range",
                    "reason": f"party {people} not in [{rules.min_party},{rules.max_party}]",
                },
            )

    # 3) Controllo step (slot_step_min)
    step = int(getattr(rules, "slot_step_min", 0) or 0)
    if step:
        m = dt_local.minute % step
        if m != 0:
            delta = step - m
            suggested = (dt_local + timedelta(minutes=delta)).strftime("%Y-%m-%dT%H:%M")
            return False, {"code": "bad_step", "suggested": suggested}

    # 4) Verifica inclusione negli slot con last_order_min
    last_order = int(getattr(rules, "last_order_min", 0) or 0)
    t_ok = False
    for s in slots_today:
        start_dt = datetime.combine(dt_local.date(), s.start, tzinfo=tz)
        end_eff = _end_effective(dt_local, s.end, last_order)
        if start_dt <= dt_local <= end_eff:
            t_ok = True
            break

    if t_ok:
        return True, {}

    # 5) Suggerisci il prossimo start utile (se siamo prima delle fasce)
    next_start = _first_future_start(dt_local, slots_today)
    if next_start:
        return False, {
            "code": "outside_hours",
            "suggested": next_start.strftime("%Y-%m-%dT%H:%M"),
        }

    # altrimenti siamo oltre l'ultima fascia del giorno
    return False, {"code": "outside_hours", "reason": "past_last_window"}

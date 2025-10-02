# -*- coding: utf-8 -*-
# backend/rules_service.py
#
# Questo modulo NON definisce più classi ORM.
# Re-esporta i modelli dal modulo centrale backend.models
# per evitare tabelle duplicate in SQLAlchemy MetaData.

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
    "OpeningHour",
    "SpecialDay",
    "RestaurantSetting",
    "Reservation",
    "ReservationPizza",
    "Pizza",
    "Restaurant",
]

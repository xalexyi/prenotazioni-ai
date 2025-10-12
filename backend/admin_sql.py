"""
Utility di amministrazione DB (migrazioni leggere + seed) per Prenotazioni-AI.

USO SU RENDER (Shell):
  python -m backend.admin_sql --seed \
    --rest-name "Haru Asian Fusion Restaurant" \
    --username "haru-admin" \
    --password "Haru!2025" \
    --logo "img/logo_sushi.svg"

Tutte le operazioni sono idempotenti: possono essere rilanciate senza rompere dati.
"""

from __future__ import annotations
import argparse
from typing import Optional

from sqlalchemy import text, inspect

# Importo l'app factory e l'istanza db già condivisa dal progetto
from app import create_app, db  # type: ignore


# ---------------------------- MIGRAZIONI “SOFT” ----------------------------- #

def add_column_if_missing(table: str, coldef_sql: str) -> None:
    """
    Aggiunge una colonna con SQL grezzo in modo idempotente.
    Funziona su PostgreSQL (Render) grazie a "IF NOT EXISTS".
    Esempio: add_column_if_missing('user', 'password_hash TEXT')
    """
    with db.engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS {coldef_sql};'))


def create_index_if_missing(index_name: str, table: str, expr: str) -> None:
    """
    Crea un indice se non esiste.
    Esempio: create_index_if_missing('idx_reservation_rest_date', 'reservation', 'restaurant_id, date, time')
    """
    with db.engine.begin() as conn:
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS {index_name} ON "{table}" ({expr});'))


def ensure_schema() -> None:
    """
    Crea tabelle dai modelli e colonne chiave se mancanti.
    """
    from backend import models  # import locale per evitare import circolari

    # 1) Assicura tabelle base
    db.create_all()

    # 2) Colonne utili che abbiamo visto mancanti in alcuni deploy
    add_column_if_missing("user", "password_hash TEXT")
    add_column_if_missing("restaurant", "weekly_hours_json TEXT")

    # 3) Indici utili
    create_index_if_missing("idx_reservation_rest_date", "reservation", "restaurant_id, date, time")
    create_index_if_missing("idx_special_day_rest_date", "special_day", "restaurant_id, date")


# ------------------------------ SEED / DATI -------------------------------- #

def ensure_settings_for_restaurant(rest_id: int):
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


def seed_restaurant_and_user(rest_name: str, username: str, password: str, logo_path: Optional[str] = None) -> None:
    """
    Crea/aggiorna ristorante + utente admin con password_hash.
    """
    from werkzeug.security import generate_password_hash
    from backend.models import Restaurant, User

    rest = Restaurant.query.filter_by(name=rest_name).first()
    if not rest:
        rest = Restaurant(name=rest_name, logo_path=(logo_path or "img/logo_robot.svg"))
        db.session.add(rest)
        db.session.commit()
        print(f"[OK] Creato Restaurant id={rest.id}")
    else:
        if logo_path and rest.logo_path != logo_path:
            rest.logo_path = logo_path
            db.session.commit()
        print(f"[OK] Restaurant esistente id={rest.id}")

    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(
            username=username,
            restaurant_id=rest.id,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        print(f"[OK] Creato User id={user.id} username={username} (rest_id={rest.id})")
    else:
        user.password_hash = generate_password_hash(password)
        user.restaurant_id = rest.id
        db.session.commit()
        print(f"[OK] Password aggiornata per {username} (rest_id={rest.id})")

    ensure_settings_for_restaurant(rest.id)


# ----------------------------- DIAGNOSTICA --------------------------------- #

def print_diagnostics() -> None:
    insp = inspect(db.engine)
    tables = insp.get_table_names()
    print("=== TABELLE PRESENTI ===")
    print(tables)
    keys = ["user", "restaurant", "reservation", "opening_hours", "special_day", "settings", "menu_item", "active_calls"]
    for t in keys:
        if t in tables:
            cols = [c["name"] for c in insp.get_columns(t)]
            print(f" - {t}: {cols}")
        else:
            print(f" - {t}: [MANCANTE]")

    try:
        rows = db.session.execute(text('select id, name from restaurant limit 5')).fetchall()
        print("restaurant sample:", rows)
        rows = db.session.execute(text('select id, username, restaurant_id from "user" limit 5')).fetchall()
        print("user sample:", rows)
    except Exception as e:
        print("[WARN] diagnostica dati:", e)


# ------------------------------- CLI --------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description="Admin SQL helper per Prenotazioni-AI")
    parser.add_argument("--seed", action="store_true", help="Esegue seed ristorante + utente")
    parser.add_argument("--rest-name", type=str, default="Haru Asian Fusion Restaurant")
    parser.add_argument("--username", type=str, default="haru-admin")
    parser.add_argument("--password", type=str, default="Haru!2025")
    parser.add_argument("--logo", type=str, default="img/logo_sushi.svg")
    parser.add_argument("--diag", action="store_true", help="Stampa diagnostica tabelle/colonne")

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        ensure_schema()
        if args.seed:
            seed_restaurant_and_user(args.rest_name, args.username, args.password, args.logo)
        if args.diag:
            print_diagnostics()

        print("[DONE] Migrazione + (eventuale) seed completati.")


if __name__ == "__main__":
    main()

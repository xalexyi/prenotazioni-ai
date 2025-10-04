# manage.py
import os
import re
import click
from werkzeug.security import generate_password_hash

from backend import create_app
from backend.models import (
    db,
    Restaurant,
    Reservation,
    Pizza,
    ReservationPizza,
    InboundNumber,
)

app = create_app()


def _ensure_instance_dir():
    """
    Se il DB è configurato come sqlite:///instance/<file>.db
    crea la cartella instance/ se non esiste.
    """
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if db_uri.startswith("sqlite:///instance/"):
        os.makedirs("instance", exist_ok=True)


# ---------------------------
# DB
# ---------------------------

@app.cli.command("create-db")
def create_db():
    """Crea tutte le tabelle del database (db.create_all)."""
    _ensure_instance_dir()
    with app.app_context():
        db.create_all()
        click.secho("✅ DB creato.", fg="green")


@app.cli.command("drop-db")
def drop_db():
    """Elimina tutte le tabelle del database."""
    with app.app_context():
        db.drop_all()
        click.secho("🗑️  DB droppato.", fg="yellow")


# ---------------------------
# DEMO DATA
# ---------------------------

@app.cli.command("seed-demo")
def seed_demo():
    """
    Resetta il DB e inserisce dati di demo:
    - 2 ristoranti (Sushi Tokyo, Pizzeria Napoli)
    - menu pizze per Pizzeria Napoli
    - numeri reali di esempio (aggiorna con i tuoi)
    """
    _ensure_instance_dir()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Ristoranti demo
        r1 = Restaurant(
            name="Sushi Tokyo",
            slug="sushitokyo",
            username="sushitokyo",
            password_hash=generate_password_hash("Password123!"),
            logo="logo_sushi.svg",
        )
        r2 = Restaurant(
            name="Pizzeria Napoli",
            slug="pizzerianapoli",
            username="pizzerianapoli",
            password_hash=generate_password_hash("Password123!"),
            logo="logo_pizzeria.svg",
        )
        db.session.add_all([r1, r2])
        db.session.flush()

        # Menù pizzeria (demo)
        pizza_menu = [
            ("Margherita", 7), ("Marinara", 6), ("Diavola", 8),
            ("Quattro Formaggi", 9), ("Capricciosa", 9),
            ("Prosciutto e Funghi", 9), ("Quattro Stagioni", 9),
            ("Napoli", 8), ("Vegetariana", 8), ("Bufalina", 10),
        ]
        db.session.add_all([
            Pizza(restaurant_id=r2.id, name=n, price=p) for n, p in pizza_menu
        ])

        # Numeri reali demo (sostituisci con i tuoi numeri E.164)
        db.session.add_all([
            InboundNumber(restaurant_id=r1.id, e164_number="+390212345678", note="Sushi - numero reale"),
            InboundNumber(restaurant_id=r2.id, e164_number="+390811234567", note="Pizzeria - numero reale"),
        ])
        db.session.commit()

        click.secho("🌱 Dati demo inseriti.", fg="green")
        click.echo("Credenziali:")
        click.echo(" - sushitokyo / Password123!")
        click.echo(" - pizzerianapoli / Password123!")
        click.echo("Aggiorna i numeri reali in 'inbound_numbers' con i tuoi veri numeri E.164.")


# ---------------------------
# LIST / UTILITY
# ---------------------------

@app.cli.command("list")
def list_all():
    """Elenca i ristoranti presenti nel DB."""
    with app.app_context():
        rows = Restaurant.query.all()
        if not rows:
            click.secho("Nessun ristorante.", fg="yellow")
            return
        for r in rows:
            click.echo(f"- {r.name} ({r.slug})  user={r.username}  logo={r.logo or '-'}")


@app.cli.command("reset-password")
@click.option("--username", required=True, help="Username del ristorante")
@click.option("--password", required=True, help="Nuova password in chiaro (verrà hashata)")
def reset_password(username, password):
    """Aggiorna la password (hash) per un ristorante."""
    with app.app_context():
        r = Restaurant.query.filter_by(username=username).first()
        if not r:
            click.secho("Username non trovato", fg="red")
            return
        r.password_hash = generate_password_hash(password)
        db.session.commit()
        click.secho("✅ Password aggiornata.", fg="green")


# ---------------------------
# NUMERI REALI ↔ RISTORANTE
# ---------------------------

_E164_RE = re.compile(r"^\+[1-9]\d{6,15}$")

@app.cli.command("link-number")
@click.option("--username", required=True, help="Username ristorante (es. pizzerianapoli)")
@click.option("--number", required=True, help="Numero reale in E.164 (es. +390811234567)")
@click.option("--note", default="", help="Nota opzionale")
def link_number(username, number, note):
    """
    Collega/aggiorna un numero reale (E.164) ad un ristorante.
    """
    with app.app_context():
        r = Restaurant.query.filter_by(username=username).first()
        if not r:
            click.secho("Ristorante non trovato", fg="red")
            return
        if not _E164_RE.match(number or ""):
            click.secho("Usa formato E.164, es: +390811234567", fg="yellow")
            return
        ex = InboundNumber.query.filter_by(e164_number=number).first()
        if ex:
            ex.restaurant_id = r.id
            ex.note = note
            ex.active = True
            click.secho("Numero aggiornato ↺", fg="cyan")
        else:
            db.session.add(InboundNumber(
                restaurant_id=r.id, e164_number=number, note=note, active=True
            ))
            click.secho("Numero collegato ✅", fg="green")
        db.session.commit()


@app.cli.command("list-numbers")
def list_numbers():
    """Elenca tutti i numeri reali registrati."""
    with app.app_context():
        rows = InboundNumber.query.order_by(InboundNumber.e164_number.asc()).all()
        if not rows:
            click.echo("Nessun numero registrato.")
            return
        for n in rows:
            click.echo(
                f"{n.e164_number} -> restaurant_id={n.restaurant_id} "
                f"({'attivo' if n.active else 'OFF'}) note={n.note or ''}"
            )


# ---------------------------
# CREA RISTORANTE
# ---------------------------

@app.cli.command("create-restaurant")
@click.argument("name")
@click.argument("username")
@click.argument("password")
def create_restaurant(name, username, password):
    """
    Crea un ristorante con username/password (password hashata).
    Esempio:
      flask create-restaurant "Haru Asian Fusion Restaurant" haru_admin 'Haru!2025'
    """
    with app.app_context():
        if Restaurant.query.filter_by(username=username).first():
            click.secho("⚠️ Username già esistente", fg="yellow")
            return
        r = Restaurant(
            name=name,
            slug=username.lower().replace(" ", "-"),
            username=username,
            password_hash=generate_password_hash(password),
            logo="logo_sushi.svg",  # default; cambialo se vuoi
        )
        db.session.add(r)
        db.session.commit()
        click.secho(f"✅ Creato ristorante '{name}' con username='{username}'", fg="green")


if __name__ == "__main__":
    # Avvio rapido: python manage.py
    # Nota: per i comandi CLI usa "flask <cmd>" con FLASK_APP=manage.py
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5001)), debug=True)

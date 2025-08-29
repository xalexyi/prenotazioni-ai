from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# ============== ACCOUNT (login) ==============
class Restaurant(UserMixin, db.Model):
    __tablename__ = "restaurants"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    logo = db.Column(db.String(120), nullable=True)

    reservations = db.relationship("Reservation", backref="restaurant", lazy=True, cascade="all, delete-orphan")
    pizzas = db.relationship("Pizza", backref="restaurant", lazy=True, cascade="all, delete-orphan")
    inbound_numbers = db.relationship("InboundNumber", backref="restaurant", lazy=True, cascade="all, delete-orphan")
    # nuove: chiamate
    call_logs = db.relationship("CallLog", backref="restaurant", lazy=True, cascade="all, delete-orphan")

# ============== PRENOTAZIONI ==============
class Reservation(db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(60), nullable=True)
    date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    time = db.Column(db.String(5), nullable=False)   # HH:MM
    people = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending|confirmed|rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pizzas = db.relationship("ReservationPizza", backref="reservation", lazy=True, cascade="all, delete-orphan")

# ============== MENU PIZZERIA ==============
class Pizza(db.Model):
    __tablename__ = "pizzas"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Integer, nullable=False, default=8)

class ReservationPizza(db.Model):
    __tablename__ = "reservation_pizzas"
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), nullable=False)
    pizza_id = db.Column(db.Integer, db.ForeignKey("pizzas.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    pizza = db.relationship("Pizza")

# ============== NUMERI REALI → RISTORANTE ==============
class InboundNumber(db.Model):
    """
    Mappa il 'numero chiamato' reale (E.164, es: +390811234567) al restaurant_id.
    Ogni ristorante può avere 1..n numeri reali che inoltrano verso Twilio.
    """
    __tablename__ = "inbound_numbers"
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    e164_number = db.Column(db.String(32), unique=True, nullable=False)  # es: +390811234567
    note = db.Column(db.String(200), nullable=True)
    active = db.Column(db.Boolean, default=True)

# ============== SESSIONE CHIAMATA (facoltativo ma utile) ==============
class CallSession(db.Model):
    """
    Mantiene lo stato per la durata della chiamata (Twilio CallSid).
    Così possiamo ricordare restaurant_id, eventuale testo raccolto, ecc.
    """
    __tablename__ = "call_sessions"
    id = db.Column(db.Integer, primary_key=True)
    call_sid = db.Column(db.String(64), unique=True, nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    step = db.Column(db.String(32), default="start")  # start|gathered|done
    collected_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============== LOG CHIAMATE/TRASCRIZIONI ==============
class CallLog(db.Model):
    __tablename__ = "call_logs"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=True)

    call_sid = db.Column(db.String(64), index=True)
    from_number = db.Column(db.String(32))
    to_number = db.Column(db.String(32))

    recording_sid = db.Column(db.String(64))
    recording_url = db.Column(db.String(512))
    duration_seconds = db.Column(db.Integer)

    transcript = db.Column(db.Text)
    received_at = db.Column(db.DateTime)                 # timestamp inviato da n8n
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

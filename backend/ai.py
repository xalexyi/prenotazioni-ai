import os
import re
import json
from datetime import date, timedelta, datetime
from flask import Blueprint, current_app
from backend.models import db, Restaurant, Reservation, ReservationPizza, Pizza

# Se hai l'SDK OpenAI installato:
# pip install openai
# from openai import OpenAI
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ai_bp = Blueprint("ai_bp", __name__)

# ---- fallback parser semplice, se non vuoi usare subito OpenAI ----
def _naive_parse(text: str):
    """
    Estrae (in modo semplice) persone, data, ora, nome, telefono, pizze.
    NOTA: è volutamente semplice; useremo OpenAI appena metti la chiave.
    """
    t = text.lower()

    # persone
    m_people = re.search(r"(\d+)\s*(persone|pers|pax)", t)
    people = int(m_people.group(1)) if m_people else 2

    # orario hh:mm
    m_time = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t)
    time_str = f"{m_time.group(1).zfill(2)}:{m_time.group(2)}" if m_time else "20:00"

    # data: "domani" / "oggi" (semplificato)
    if "domani" in t:
        d = (date.today() + timedelta(days=1)).isoformat()
    elif "oggi" in t:
        d = date.today().isoformat()
    else:
        # se non riconosce, mettiamo oggi
        d = date.today().isoformat()

    # nome (grezzo): dopo "mi chiamo"
    name = "Cliente"
    m_name = re.search(r"mi chiamo\s+([a-zA-Zàèéìòùç' ]+)", t)
    if m_name:
        name = m_name.group(1).strip().title()

    # telefono (se c'è)
    m_phone = re.search(r"(?:\+?\d[\d\s]{6,}\d)", text)
    phone = m_phone.group(0).replace(" ", "") if m_phone else ""

    # pizze: cerca pattern "margherita x2", "2 margherita"
    pizzas = []
    known = ["margherita","marinara","diavola","quattro formaggi","capricciosa",
             "prosciutto e funghi","quattro stagioni","napoli","vegetariana","bufalina"]
    for name_p in known:
        # x2
        m1 = re.search(rf"{name_p}\s*[x×]\s*(\d+)", t)
        # 2 margherita
        m2 = re.search(rf"(\d+)\s+{name_p}", t)
        qty = None
        if m1: qty = int(m1.group(1))
        elif m2: qty = int(m2.group(1))
        if qty:
            pizzas.append({"name": name_p.title(), "qty": qty})

    return {
        "customer_name": name or "Cliente",
        "phone": phone,
        "date": d,
        "time": time_str,
        "people": people,
        "pizzas": pizzas,  # solo pizzeria userà questo
    }

def parse_with_ai(text: str):
    """
    Qui useremo OpenAI per un parsing affidabile.
    Se non hai ancora OPENAI_API_KEY, usa _naive_parse.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return _naive_parse(text)

    # ESEMPIO (commentato) di uso OpenAI:
    # prompt = f"""
    # Estrai da questo testo una prenotazione ristorante.
    # Rispondi in JSON con campi: customer_name, phone, date(YYYY-MM-DD), time(HH:MM), people, pizzas=[{{name, qty}}].
    # Testo: {text}
    # """
    # chat = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=[{"role":"system","content":"Sei un assistente che estrae dati strutturati."},
    #               {"role":"user","content":prompt}],
    #     temperature=0.1
    # )
    # raw = chat.choices[0].message.content
    # try:
    #     data = json.loads(raw)
    # except:
    #     data = _naive_parse(text)
    # return data
    return _naive_parse(text)

def create_reservation_db(restaurant: Restaurant, parsed: dict):
    """
    Crea la prenotazione nel DB (e associa pizze se è una pizzeria con menu).
    """
    res = Reservation(
        restaurant_id=restaurant.id,
        customer_name=parsed.get("customer_name") or "Cliente",
        phone=parsed.get("phone") or "",
        date=parsed.get("date"),
        time=parsed.get("time"),
        people=int(parsed.get("people") or 2),
        status="pending"
    )
    db.session.add(res)
    db.session.flush()

    # Se il ristorante ha un menu pizze, prova a collegare le pizze
    pizzas = parsed.get("pizzas") or []
    if pizzas:
        menu = {p.name.lower(): p for p in Pizza.query.filter_by(restaurant_id=restaurant.id).all()}
        for item in pizzas:
            n = (item.get("name") or "").lower()
            q = int(item.get("qty") or 0)
            if n in menu and q > 0:
                db.session.add(ReservationPizza(reservation_id=res.id, pizza_id=menu[n].id, quantity=q))

    db.session.commit()
    return res.id

# backend/ai.py
import os
import re
import json
from typing import Dict, List, Optional, Tuple, Any

from datetime import date, timedelta, datetime
from flask import Blueprint, current_app, request, jsonify

from backend.models import db, Restaurant, Reservation, ReservationPizza, Pizza

# Se vuoi usare OpenAI: pip install openai
# Il codice tenta l'import dinamico solo se c'è OPENAI_API_KEY
_OPENAI_AVAILABLE = False
try:
    from openai import OpenAI  # type: ignore
    _OPENAI_AVAILABLE = True
except Exception:
    _OPENAI_AVAILABLE = False

ai_bp = Blueprint("ai_bp", __name__)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-]{6,}\d)")

def _hhmm(s: str, default: str = "20:00") -> str:
    """
    Normalizza orario HH:MM. Se non conforme, torna default.
    """
    if not s:
        return default
    s = s.strip()
    m = _TIME_RE.match(s)
    if not m:
        return default
    return f"{m.group(1).zfill(2)}:{m.group(2)}"

def _rel_date_from_words(text: str) -> str:
    """
    Converte parole semplici ('oggi', 'domani', 'dopodomani') in YYYY-MM-DD.
    Se non trova nulla, ritorna la data di oggi.
    """
    t = text.lower()
    if "dopodomani" in t:
        return (date.today() + timedelta(days=2)).isoformat()
    if "domani" in t:
        return (date.today() + timedelta(days=1)).isoformat()
    if "oggi" in t:
        return date.today().isoformat()
    # fallback: oggi
    return date.today().isoformat()

def _extract_phone(raw: str) -> str:
    m = _PHONE_RE.search(raw or "")
    if not m:
        return ""
    return re.sub(r"\s+", "", m.group(0)).replace("-", "")

# ---------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------
def _naive_parse(text: str) -> Dict[str, Any]:
    """
    Estrae (in modo semplice) persone, data, ora, nome, telefono, pizze.
    NOTA: volutamente semplice; useremo OpenAI appena metti la chiave.
    """
    t = (text or "").strip()
    tl = t.lower()

    # persone
    m_people = re.search(r"(\d+)\s*(persone|pers|pax)", tl)
    people = int(m_people.group(1)) if m_people else 2

    # orario hh:mm
    m_time = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", tl)
    time_str = _hhmm(f"{m_time.group(1)}:{m_time.group(2)}") if m_time else "20:00"

    # data: parole chiave semplici (oggi / domani / dopodomani)
    d = _rel_date_from_words(tl)

    # nome (grezzo): dopo "mi chiamo"
    name = "Cliente"
    m_name = re.search(r"mi chiamo\s+([a-zA-Zàèéìòùç' ]+)", tl)
    if m_name:
        name = m_name.group(1).strip().title()

    # telefono
    phone = _extract_phone(t)

    # pizze: cerca pattern "margherita x2", "2 margherita"
    pizzas: List[Dict[str, Any]] = []
    known = [
        "margherita", "marinara", "diavola", "quattro formaggi", "capricciosa",
        "prosciutto e funghi", "quattro stagioni", "napoli", "vegetariana", "bufalina"
    ]
    for name_p in known:
        # x2
        m1 = re.search(rf"{re.escape(name_p)}\s*[x×]\s*(\d+)", tl)
        # 2 margherita
        m2 = re.search(rf"(\d+)\s+{re.escape(name_p)}", tl)
        qty = None
        if m1:
            qty = int(m1.group(1))
        elif m2:
            qty = int(m2.group(1))
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

def parse_with_ai(text: str) -> Dict[str, Any]:
    """
    Parser “AI-first” con fallback naif se non c'è API key o libreria.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not _OPENAI_AVAILABLE:
        return _naive_parse(text)

    try:
        client = OpenAI(api_key=api_key)
        prompt = (
            "Estrai da questo testo una prenotazione ristorante. "
            "Rispondi in JSON con campi: "
            "customer_name, phone, date(YYYY-MM-DD), time(HH:MM), people, "
            "pizzas=[{name, qty}]. "
            f"Testo: {text}"
        )
        chat = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sei un assistente che estrae dati strutturati."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        raw = chat.choices[0].message.content
        data = json.loads(raw)
        # Hardening minimo sui campi critici
        data["time"] = _hhmm(str(data.get("time", "20:00")))
        data["date"] = str(data.get("date") or _rel_date_from_words(text))
        data["people"] = int(data.get("people") or 2)
        data["customer_name"] = (data.get("customer_name") or "Cliente").strip() or "Cliente"
        data["phone"] = _extract_phone(data.get("phone") or text)
        if "pizzas" in data and not isinstance(data["pizzas"], list):
            data["pizzas"] = []
        return data
    except Exception:
        return _naive_parse(text)

# ---------------------------------------------------------------------
# DB writer
# ---------------------------------------------------------------------
def create_reservation_db(restaurant: Restaurant, parsed: Dict[str, Any]) -> int:
    """
    Crea la prenotazione nel DB (e associa pizze se è una pizzeria con menu).
    """
    res = Reservation(
        restaurant_id=restaurant.id,
        customer_name=parsed.get("customer_name") or "Cliente",
        phone=parsed.get("phone") or "",
        date=str(parsed.get("date") or date.today().isoformat()),
        time=_hhmm(str(parsed.get("time") or "20:00")),
        people=int(parsed.get("people") or 2),
        status="pending",
    )
    db.session.add(res)
    db.session.flush()

    # Se il ristorante ha un menu pizze, prova a collegare le pizze
    pizzas = parsed.get("pizzas") or []
    if pizzas:
        menu = {p.name.lower(): p for p in Pizza.query.filter_by(restaurant_id=restaurant.id).all()}
        for item in pizzas:
            n = (item.get("name") or "").lower().strip()
            q = int(item.get("qty") or 0)
            if n in menu and q > 0:
                db.session.add(
                    ReservationPizza(reservation_id=res.id, pizza_id=menu[n].id, quantity=q)
                )

    db.session.commit()
    return res.id

# ---------------------------------------------------------------------
# API endpoints (opzionali ma utili per n8n/test)
# ---------------------------------------------------------------------
@ai_bp.post("/api/ai/parse")
def api_ai_parse():
    """
    Body JSON: { "text": "..." }
    Ritorna:   { "ok": true, "parsed": {...} }
    """
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "missing text"}), 400
    parsed = parse_with_ai(text)
    return jsonify({"ok": True, "parsed": parsed}), 200


@ai_bp.post("/api/ai/create")
def api_ai_create():
    """
    Body JSON:
    {
      "restaurant_id": 1,
      "text": "vorrei prenotare ...",
      // opzionali override dei campi già parsati:
      "override": { "date": "2025-08-15", "time": "20:30", "people": 4 }
    }

    Effettua il parse (AI o naive), applica eventuali override e crea la prenotazione.
    """
    data = request.get_json(force=True, silent=True) or {}
    rid = int(data.get("restaurant_id") or 0)
    text = (data.get("text") or "").strip()
    override = data.get("override") or {}

    if not rid:
        return jsonify({"ok": False, "error": "missing restaurant_id"}), 400
    if not text:
        return jsonify({"ok": False, "error": "missing text"}), 400

    r = Restaurant.query.get(rid)
    if not r:
        return jsonify({"ok": False, "error": "restaurant_not_found"}), 404

    parsed = parse_with_ai(text)

    # Applica override sicuri
    for k, v in override.items():
        parsed[k] = v

    try:
        new_id = create_reservation_db(r, parsed)
        return jsonify({"ok": True, "id": new_id, "parsed": parsed}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "detail": str(e)}), 500

# -*- coding: utf-8 -*-
# backend/twilio_voice.py
from __future__ import annotations

from flask import Blueprint, request, Response, url_for
from twilio.twiml.voice_response import VoiceResponse, Gather

from backend.models import db, InboundNumber, Restaurant, CallSession
from backend.ai import parse_with_ai, create_reservation_db

twilio_bp = Blueprint("twilio", __name__, url_prefix="/twilio")


def _norm_e164(num: str | None) -> str:
    """Normalizza un numero in forma E.164 rimuovendo spazi e trattini."""
    if not num:
        return ""
    return num.replace(" ", "").replace("-", "")


def _find_restaurant_by_to_number(to_number: str | None) -> Restaurant | None:
    """
    Trova il ristorante in base al numero 'To' (numero reale del ristorante).
    """
    e164 = _norm_e164(to_number)
    if not e164:
        return None
    mapping = InboundNumber.query.filter_by(e164_number=e164, active=True).first()
    return mapping.restaurant if mapping else None


@twilio_bp.route("/voice", methods=["POST", "GET"])
def voice():
    """
    Primo hook: entra la chiamata.
    - Identifica il ristorante dal numero 'To'/'Called'
    - Apre un Gather (speech) e inoltra a /twilio/handle
    """
    # Twilio normalmente usa POST; se arriva GET, gestiamo uguale.
    to_number = request.values.get("To") or request.values.get("Called")
    call_sid = request.values.get("CallSid")

    vr = VoiceResponse()
    restaurant = _find_restaurant_by_to_number(to_number)

    if not restaurant:
        vr.say(language="it-IT", message="Spiacente. Numero non riconosciuto. Arrivederci.")
        vr.hangup()
        return Response(str(vr), mimetype="text/xml")

    # Registra/aggiorna sessione chiamata
    sess = CallSession.query.filter_by(call_sid=call_sid).first()
    if not sess:
        sess = CallSession(call_sid=call_sid, restaurant_id=restaurant.id, step="start")
        db.session.add(sess)
        db.session.commit()

    # Messaggio di benvenuto dinamico
    benv = (
        f"Ciao! Hai chiamato {restaurant.name}. "
        "Dimmi come posso aiutarti: ad esempio, "
        "vorrei prenotare domani alle 20 per tre persone, "
        "oppure vorrei ordinare due Margherite e una Diavola."
    )

    # URL assoluto (Twilio richiede endpoint pubblici)
    action_url = url_for("twilio.handle", _external=True)

    gather = Gather(
        input="speech",
        language="it-IT",
        hints="prenotare, ordinare, oggi, domani, dopodomani, margherita, diavola, quattro formaggi, persone",
        speech_timeout="auto",
        action=action_url,
        method="POST",
    )
    gather.say(language="it-IT", message=benv)
    vr.append(gather)

    # Fallback: nessun input ricevuto
    vr.say(language="it-IT", message="Non ti ho sentito. Riprova più tardi. Arrivederci.")
    vr.hangup()
    return Response(str(vr), mimetype="text/xml")


@twilio_bp.route("/handle", methods=["POST"])
def handle():
    """
    Secondo hook: riceve lo SpeechResult, fa il parse, salva la prenotazione
    e fornisce una conferma vocale.
    """
    call_sid = request.values.get("CallSid")
    speech = (request.values.get("SpeechResult") or "").strip()

    vr = VoiceResponse()
    sess = CallSession.query.filter_by(call_sid=call_sid).first()

    if not sess:
        vr.say(language="it-IT", message="Si è verificato un errore di sessione. Riprova più tardi.")
        vr.hangup()
        return Response(str(vr), mimetype="text/xml")

    restaurant = Restaurant.query.get(sess.restaurant_id)
    if not restaurant:
        vr.say(language="it-IT", message="Ristorante non trovato. Arrivederci.")
        vr.hangup()
        return Response(str(vr), mimetype="text/xml")

    if not speech:
        vr.say(language="it-IT", message="Mi dispiace, non ho capito. Riprova più tardi.")
        vr.hangup()
        # Chiudi la sessione per non lasciarla appesa
        sess.step = "done"
        db.session.commit()
        return Response(str(vr), mimetype="text/xml")

    # Parsing (AI-first con fallback locale)
    parsed = parse_with_ai(speech)

    try:
        res_id = create_reservation_db(restaurant, parsed)
    except Exception:
        vr.say(language="it-IT", message="Non sono riuscito a registrare la prenotazione. Riprova più tardi.")
        vr.hangup()
        # Chiudi sessione anche in caso d'errore
        sess.step = "done"
        sess.collected_text = speech
        db.session.commit()
        return Response(str(vr), mimetype="text/xml")

    # Conferma vocale
    nome = parsed.get("customer_name") or "Cliente"
    when = f"{parsed.get('date')} alle {parsed.get('time')}"
    people = parsed.get("people") or 2
    vr.say(language="it-IT", message=f"{nome}, ho registrato la tua richiesta per {people} persone il {when}.")
    vr.say(language="it-IT", message="Riceverai una conferma appena possibile. Grazie e a presto!")
    vr.hangup()

    # Aggiorna sessione
    sess.step = "done"
    sess.collected_text = speech
    db.session.commit()

    return Response(str(vr), mimetype="text/xml")

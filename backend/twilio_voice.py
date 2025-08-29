from flask import Blueprint, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from backend.models import db, InboundNumber, Restaurant, CallSession
from .ai import parse_with_ai, create_reservation_db

twilio_bp = Blueprint("twilio", __name__, url_prefix="/twilio")

def _norm_e164(num: str) -> str:
    """Normalizza un numero in forma E.164 senza spazi."""
    return (num or "").replace(" ", "").replace("-", "")

def _find_restaurant_by_to_number(to_number: str):
    """Trova il ristorante in base al numero 'To' (il numero reale del ristorante che ha inoltrato a Twilio)."""
    e164 = _norm_e164(to_number)
    mapping = InboundNumber.query.filter_by(e164_number=e164, active=True).first()
    if mapping:
        return mapping.restaurant
    return None

@twilio_bp.route("/voice", methods=["POST", "GET"])
def voice():
    """
    Primo hook: entra la chiamata.
    Identifichiamo il ristorante dal 'To' reale (numero del ristorante) e avviamo un Gather.
    """
    to_number = request.values.get("To") or request.values.get("Called")
    call_sid = request.values.get("CallSid")

    restaurant = _find_restaurant_by_to_number(to_number)
    vr = VoiceResponse()

    if not restaurant:
        vr.say(language="it-IT", message="Spiacente. Numero non riconosciuto. Arrivederci.")
        vr.hangup()
        return Response(str(vr), mimetype="text/xml")

    # Registra/aggiorna sessione
    sess = CallSession.query.filter_by(call_sid=call_sid).first()
    if not sess:
        sess = CallSession(call_sid=call_sid, restaurant_id=restaurant.id, step="start")
        db.session.add(sess)
        db.session.commit()

    # Messaggio contestuale per quel ristorante
    benv = f"Ciao! Hai chiamato {restaurant.name}. "
    benv += "Dimmi come posso aiutarti: ad esempio, 'voglio prenotare domani alle 20 per 3 persone', "
    benv += "oppure 'vorrei ordinare due Margherite e una Diavola'."

    gather = Gather(
        input="speech",
        language="it-IT",
        hints="prenotare, ordinare, domani, oggi, margherita, diavola, quattro formaggi, persone",
        speech_timeout="auto",
        action="/twilio/handle",
        method="POST"
    )
    gather.say(language="it-IT", message=benv)
    vr.append(gather)

    vr.say(language="it-IT", message="Non ti ho sentito. Riprova più tardi. Ciao!")
    vr.hangup()
    return Response(str(vr), mimetype="text/xml")

@twilio_bp.route("/handle", methods=["POST"])
def handle():
    """
    Secondo hook: riceve lo SpeechResult, usa AI per estrarre dati,
    salva la prenotazione su DB e conferma a voce.
    """
    call_sid = request.values.get("CallSid")
    speech = request.values.get("SpeechResult") or ""

    sess = CallSession.query.filter_by(call_sid=call_sid).first()
    vr = VoiceResponse()

    if not sess:
        vr.say(language="it-IT", message="Si è verificato un errore di sessione. Riprova più tardi.")
        vr.hangup()
        return Response(str(vr), mimetype="text/xml")

    restaurant = Restaurant.query.get(sess.restaurant_id)
    if not restaurant:
        vr.say(language="it-IT", message="Ristorante non trovato. Arrivederci.")
        vr.hangup()
        return Response(str(vr), mimetype="text/xml")

    # Parsing AI
    parsed = parse_with_ai(speech)

    try:
        res_id = create_reservation_db(restaurant, parsed)
    except Exception as e:
        vr.say(language="it-IT", message="Non sono riuscito a registrare la prenotazione. Riprova più tardi.")
        vr.hangup()
        return Response(str(vr), mimetype="text/xml")

    # Conferma vocale
    nome = parsed.get("customer_name") or "Cliente"
    when = f"{parsed.get('date')} alle {parsed.get('time')}"
    people = parsed.get("people")
    vr.say(language="it-IT", message=f"{nome}, ho registrato la tua richiesta per {people} persone il {when}.")
    vr.say(language="it-IT", message="Riceverai conferma appena possibile. Grazie, a presto!")
    vr.hangup()

    # aggiorna sessione
    sess.step = "done"
    sess.collected_text = speech
    db.session.commit()

    return Response(str(vr), mimetype="text/xml")

# -*- coding: utf-8 -*-
# backend/dashboard.py
from __future__ import annotations

from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from datetime import datetime, date, timedelta
from sqlalchemy import func

from backend.models import db, Restaurant, Reservation

dashboard = Blueprint("dashboard", __name__, url_prefix="/dashboard")

# ============================================================
#  Funzioni helper
# ============================================================

def _require_login():
    """Controlla se l'utente è loggato"""
    rid = session.get("user_id")
    if not rid:
        return None
    return Restaurant.query.get(rid)

# ============================================================
#  Dashboard principale
# ============================================================

@dashboard.route("/")
def dashboard_view():
    """Pagina principale con riepilogo prenotazioni"""
    user = _require_login()
    if not user:
        return redirect(url_for("auth.login"))

    # Filtri base (oggi / ultimi 30 giorni)
    rng = request.args.get("range", "today")
    base_q = Reservation.query.filter_by(restaurant_id=user.id)

    today = date.today()
    if rng == "today":
        base_q = base_q.filter(Reservation.date == today.isoformat())
    elif rng == "last30":
        start = today - timedelta(days=30)
        base_q = base_q.filter(Reservation.date >= start.isoformat())

    reservations = base_q.order_by(Reservation.date.desc(), Reservation.time.asc()).all()

    # Riepilogo numerico
    total = len(reservations)
    confirmed = sum(1 for r in reservations if r.status == "confirmed")
    total_people = sum(r.people or 0 for r in reservations)

    avg_people = round(total_people / total, 1) if total else 0
    pct_confirmed = f"{round((confirmed / total) * 100)}%" if total else "0%"

    stats = {
        "total": total,
        "confirmed": confirmed,
        "people": total_people,
        "avg_people": avg_people,
        "pct_confirmed": pct_confirmed,
    }

    # Riepilogo “AI style” lato server (no LLM)
    ai_summary = (
        f"Oggi {stats['total']} prenotazioni, media {stats['avg_people']} persone, "
        f"{stats['pct_confirmed']} confermate."
        if rng == "today" else
        f"Ultimi 30 giorni: {stats['total']} prenotazioni totali, media {stats['avg_people']} persone."
    )

    return render_template(
        "dashboard.html",
        restaurant=user,
        reservations=reservations,
        stats=stats,
        ai_summary=ai_summary,
        date_today=today.strftime("%Y-%m-%d"),
        range=rng,
    )

# ============================================================
#  API Dashboard JSON (per AJAX live update)
# ============================================================

@dashboard.get("/api/data")
def dashboard_api_data():
    """Ritorna prenotazioni e statistiche in formato JSON"""
    user = _require_login()
    if not user:
        return jsonify({"ok": False, "error": "Non autenticato."}), 401

    today = date.today()
    res_today = Reservation.query.filter_by(restaurant_id=user.id, date=today.isoformat()).all()
    total = len(res_today)
    confirmed = sum(1 for r in res_today if r.status == "confirmed")
    people = sum(r.people or 0 for r in res_today)

    return jsonify({
        "ok": True,
        "date": today.isoformat(),
        "total": total,
        "confirmed": confirmed,
        "people": people,
        "avg_people": round(people / total, 1) if total else 0,
    })

# ============================================================
#  API per aggiornare status prenotazione
# ============================================================

@dashboard.post("/api/reservation/<int:res_id>/status")
def update_reservation_status(res_id: int):
    """Aggiorna stato prenotazione (confirmed/rejected/pending)"""
    user = _require_login()
    if not user:
        return jsonify({"ok": False, "error": "Non autenticato"}), 401

    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in ("pending", "confirmed", "rejected"):
        return jsonify({"ok": False, "error": "Stato non valido"}), 400

    res = Reservation.query.filter_by(id=res_id, restaurant_id=user.id).first()
    if not res:
        return jsonify({"ok": False, "error": "Prenotazione non trovata"}), 404

    res.status = status
    db.session.commit()
    return jsonify({"ok": True, "id": res.id, "status": status})

# ============================================================
#  API per eliminare prenotazione
# ============================================================

@dashboard.delete("/api/reservation/<int:res_id>")
def delete_reservation(res_id: int):
    """Elimina una prenotazione"""
    user = _require_login()
    if not user:
        return jsonify({"ok": False, "error": "Non autenticato"}), 401

    res = Reservation.query.filter_by(id=res_id, restaurant_id=user.id).first()
    if not res:
        return jsonify({"ok": False, "error": "Prenotazione non trovata"}), 404

    db.session.delete(res)
    db.session.commit()
    return jsonify({"ok": True, "deleted": res_id})

# ============================================================
#  API orari suggeriti / AI (demo)
# ============================================================

@dashboard.get("/api/insights")
def get_ai_insights():
    """Simula suggerimenti AI per orari e gestione ristorante"""
    user = _require_login()
    if not user:
        return jsonify({"ok": False, "error": "Non autenticato"}), 401

    insights = [
        "Martedì sera (20:30–22:00) bassa domanda → valuta chiusura anticipata.",
        "Venerdì e Sabato tra 19:30–21:00 → aumenta capacità o aggiungi un cameriere.",
        "Domenica pranzo (12:30–13:30) molto forte → promuovi menu fisso per aumentare ticket medio.",
    ]
    return jsonify({"ok": True, "insights": insights})

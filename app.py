# app.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Dict, Any

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.security import check_password_hash

# ---------------------------------------------------------------------
# SQLAlchemy istanza "globale" (inizializzata dentro create_app)
# ---------------------------------------------------------------------
db = SQLAlchemy()


def _bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val or "").strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
        instance_relative_config=True,
    )

    # -----------------------------------------------------------------
    # Config di base sicure per locale/Render
    # -----------------------------------------------------------------
    app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret"))
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(app.instance_path, 'app.db')}")
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("REMEMBER_COOKIE_SAMESITE", "Lax")

    # Crea cartella instance se serve
    os.makedirs(app.instance_path, exist_ok=True)

    # Inizializza DB
    db.init_app(app)

    # -----------------------------------------------------------------
    # Import robusto dei modelli (funziona sia se models.py è in root
    # sia se si trova in backend/models.py)
    # -----------------------------------------------------------------
    try:
        import models as _models  # type: ignore
    except Exception:
        from backend import models as _models  # type: ignore

    # Aliases dei modelli se esistono
    User = getattr(_models, "User", None)
    Restaurant = getattr(_models, "Restaurant", None)
    Reservation = getattr(_models, "Reservation", None)
    OpeningHours = getattr(_models, "OpeningHours", None)
    SpecialDay = getattr(_models, "SpecialDay", None)

    # -----------------------------------------------------------------
    # Login manager
    # -----------------------------------------------------------------
    login_manager = LoginManager()
    login_manager.login_view = "login_page"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        """Caricatore utente sicuro: niente transazioni lasciate a metà."""
        if not User:
            return None
        try:
            return db.session.get(User, int(user_id))
        except Exception as e:
            app.logger.error("user_loader error: %s", e)
            db.session.rollback()
            return None

    # -----------------------------------------------------------------
    # Blueprints opzionali: registrali se ci sono (non crashare se mancano)
    # -----------------------------------------------------------------
    for dotted, attr in (
        ("api", "bp_api"),
        ("backend.api", "bp_api"),
        ("voice_slots", "bp_voice_slots"),
        ("backend.voice_slots", "bp_voice_slots"),
    ):
        try:
            mod = __import__(dotted, fromlist=[attr])
            bp = getattr(mod, attr, None)
            if bp:
                app.register_blueprint(bp)
                app.logger.info("Registrato blueprint %s.%s", dotted, attr)
        except Exception:
            pass  # silenzioso: non esiste → nessun problema

    # -----------------------------------------------------------------
    # Pagine
    # -----------------------------------------------------------------
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login_page"))

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        if request.method == "GET":
            if current_user.is_authenticated:
                return redirect(url_for("dashboard"))
            return render_template("login.html")

        # POST
        if not User:
            flash("Configurazione mancante: tabella utenti non trovata.")
            return render_template("login.html"), 500

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        remember = _bool(request.form.get("remember"))

        if not username or not password:
            flash("Inserisci username e password.")
            return render_template("login.html"), 400

        # tollerante a - / _
        candidates = {username, username.replace("_", "-"), username.replace("-", "_")}
        try:
            user = User.query.filter(User.username.in_(list(candidates))).first()
        except Exception as e:
            app.logger.error("login query error: %s", e)
            db.session.rollback()
            flash("Errore interno. Riprova.")
            return render_template("login.html"), 500

        if not user:
            flash("Credenziali non valide.")
            return render_template("login.html"), 401

        try:
            ok = check_password_hash(user.password, password)
        except Exception as e:
            app.logger.error("check_password_hash error: %s", e)
            ok = False

        if not ok:
            flash("Credenziali non valide.")
            return render_template("login.html"), 401

        login_user(user, remember=remember)
        return redirect(url_for("dashboard"))

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _require_models(*names: str) -> Optional[tuple]:
        missing = [n for n in names if locals().get(n) is None]
        if missing:
            return None
        return tuple(locals()[n] for n in names)  # type: ignore

    def _ensure_restaurant_id() -> Optional[int]:
        """Restituisce l'ID ristorante associato all'utente loggato."""
        if not current_user.is_authenticated:
            return None
        rid = getattr(current_user, "restaurant_id", None)
        try:
            return int(rid) if rid is not None else None
        except Exception:
            return None

    # -----------------------------------------------------------------
    # API MINIME — solo se non hai già blueprint che le gestiscono.
    # Sono in try/except e tornano 501 se il modello non esiste.
    # -----------------------------------------------------------------

    # Prenotazioni
    @app.route("/api/reservations", methods=["GET", "POST"])
    @login_required
    def api_reservations():
        pair = _require_models("Reservation")
        if not pair:
            return jsonify(ok=False, error="Not Implemented"), 501
        (ReservationModel,) = pair
        rid = _ensure_restaurant_id()
        if rid is None:
            return jsonify(ok=False, error="no_restaurant"), 400

        if request.method == "GET":
            date = request.args.get("date")
            q = (request.args.get("q") or "").strip().lower()
            qry = ReservationModel.query.filter_by(restaurant_id=rid)
            if date:
                qry = qry.filter(ReservationModel.date == date)
            items = qry.order_by(ReservationModel.time.asc()).all()
            out = []
            for r in items:
                if q:
                    blob = " ".join([
                        r.name or "", r.phone or "", r.time or "", r.date or ""
                    ]).lower()
                    if q not in blob:
                        continue
                out.append({
                    "id": r.id,
                    "date": r.date,
                    "time": r.time,
                    "name": r.name,
                    "phone": r.phone,
                    "people": r.people,
                    "status": r.status,
                    "note": r.note
                })
            return jsonify(ok=True, items=out)

        # POST: crea
        data = request.get_json(force=True, silent=True) or {}
        try:
            obj = ReservationModel(
                restaurant_id=rid,
                date=data.get("date"),
                time=data.get("time"),
                name=data.get("name"),
                phone=data.get("phone"),
                people=int(data.get("people") or 2),
                status=data.get("status") or "Confermata",
                note=data.get("note") or "",
            )
            db.session.add(obj)
            db.session.commit()
            return jsonify(ok=True, id=obj.id)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    @app.route("/api/reservations/<int:res_id>", methods=["PUT", "DELETE"])
    @login_required
    def api_reservation_item(res_id: int):
        pair = _require_models("Reservation")
        if not pair:
            return jsonify(ok=False, error="Not Implemented"), 501
        (ReservationModel,) = pair
        rid = _ensure_restaurant_id()
        if rid is None:
            return jsonify(ok=False, error="no_restaurant"), 400

        obj = ReservationModel.query.filter_by(id=res_id, restaurant_id=rid).first()
        if not obj:
            return jsonify(ok=False, error="not_found"), 404

        if request.method == "DELETE":
            try:
                db.session.delete(obj)
                db.session.commit()
                return jsonify(ok=True)
            except Exception as e:
                db.session.rollback()
                return jsonify(ok=False, error=str(e)), 400

        data = request.get_json(force=True, silent=True) or {}
        try:
            for k in ("date", "time", "name", "phone", "status", "note"):
                if k in data:
                    setattr(obj, k, data[k])
            if "people" in data:
                obj.people = int(data["people"])
            db.session.commit()
            return jsonify(ok=True)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    # Orari settimanali
    @app.route("/api/hours", methods=["POST"])
    @login_required
    def api_hours():
        pair = _require_models("OpeningHours")
        if not pair:
            return jsonify(ok=False, error="Not Implemented"), 501
        (HoursModel,) = pair
        rid = _ensure_restaurant_id()
        if rid is None:
            return jsonify(ok=False, error="no_restaurant"), 400

        data = request.get_json(force=True, silent=True) or {}
        hours: Dict[str, str] = data.get("hours") or {}
        try:
            # sovrascrivi tutte le righe per semplicità
            HoursModel.query.filter_by(restaurant_id=rid).delete()
            for day_idx, windows in hours.items():
                h = HoursModel(restaurant_id=rid, weekday=int(day_idx), windows=windows)
                db.session.add(h)
            db.session.commit()
            return jsonify(ok=True)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    # Giorni speciali
    @app.route("/api/special-days", methods=["POST"])
    @login_required
    def api_special_days():
        pair = _require_models("SpecialDay")
        if not pair:
            return jsonify(ok=False, error="Not Implemented"), 501
        (SpecialModel,) = pair
        rid = _ensure_restaurant_id()
        if rid is None:
            return jsonify(ok=False, error="no_restaurant"), 400

        data = request.get_json(force=True, silent=True) or {}
        day = data.get("day")
        closed = _bool(data.get("closed"))
        windows = data.get("windows") or ""

        if not day:
            return jsonify(ok=False, error="missing_day"), 400

        try:
            obj = SpecialModel.query.filter_by(restaurant_id=rid, day=day).first()
            if not obj:
                obj = SpecialModel(restaurant_id=rid, day=day, closed=closed, windows=windows)
                db.session.add(obj)
            else:
                obj.closed = closed
                obj.windows = windows
            db.session.commit()
            return jsonify(ok=True)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    @app.route("/api/special-days/<day>", methods=["DELETE"])
    @login_required
    def api_special_days_delete(day: str):
        pair = _require_models("SpecialDay")
        if not pair:
            return jsonify(ok=False, error="Not Implemented"), 501
        (SpecialModel,) = pair
        rid = _ensure_restaurant_id()
        if rid is None:
            return jsonify(ok=False, error="no_restaurant"), 400

        try:
            SpecialModel.query.filter_by(restaurant_id=rid, day=day).delete()
            db.session.commit()
            return jsonify(ok=True)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    # -----------------------------------------------------------------
    # Error handlers "puliti"
    # -----------------------------------------------------------------
    @app.errorhandler(401)
    def _401(_e):
        if request.accept_mimetypes.best == "application/json":
            return jsonify(ok=False, error="unauthorized"), 401
        flash("Devi effettuare il login.")
        return redirect(url_for("login_page"))

    @app.errorhandler(404)
    def _404(_e):
        if request.accept_mimetypes.best == "application/json":
            return jsonify(ok=False, error="not_found"), 404
        return render_template("404.html") if os.path.exists(
            os.path.join(app.template_folder or "templates", "404.html")
        ) else ("Pagina non trovata", 404)

    return app


# ---------------------------------------------------------------------
# Avvio locale (python app.py)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

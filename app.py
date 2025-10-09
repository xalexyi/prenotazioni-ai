import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash

# -----------------------------------------------------------------------------
# DB setup
# -----------------------------------------------------------------------------
db = SQLAlchemy()


def _normalize_db_url(url: str) -> str:
    # Render/Heroku: postgres:// -> postgresql://
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    # ------------------- Config -------------------
    database_url = _normalize_db_url(os.getenv("DATABASE_URL", ""))
    if not database_url:
        os.makedirs("instance", exist_ok=True)
        database_url = "sqlite:///instance/dev.sqlite3"

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_SORT_KEYS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

    # Init DB
    db.init_app(app)

    # ------------------- Import modelli -------------------
    # I modelli stanno nel file models.py del tuo progetto
    try:
        import models  # type: ignore
    except Exception:
        from backend import models  # type: ignore

    # ------------------- Login Manager -------------------
    login_manager = LoginManager(app)
    login_manager.login_view = "login_page"

    @login_manager.user_loader
    def load_user(user_id: str):
        # Evita transazione “sporca” se la tabella non esiste ancora
        try:
            return db.session.get(models.User, int(user_id))
        except Exception:
            db.session.rollback()
            return None

    # ------------------- Blueprint opzionali -------------------
    # Voice slots REST (già presente nel repo)
    try:
        from backend.voice_slots import bp_voice_slots  # type: ignore
    except Exception:
        from voice_slots import bp_voice_slots  # type: ignore
    app.register_blueprint(bp_voice_slots)

    # ------------------- Healthcheck -------------------
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # ------------------- Routing: login come homepage -------------------
    @app.route("/", methods=["GET"])
    def login_page():
        # se già loggato → dashboard
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.post("/login")
    def login_post():
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        user = models.User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            return render_template("login.html", error="Credenziali non valide.")

        login_user(user, remember=bool(request.form.get("remember")))
        return redirect(url_for("dashboard"))

    @app.get("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    # ------------------- Dashboard (protetta) -------------------
    @app.get("/dashboard")
    @login_required
    def dashboard():
        # carica qualche dato base
        rest = models.Restaurant.query.get(current_user.restaurant_id)
        return render_template("dashboard.html", restaurant=rest)

    # =========================================================================
    # ===============            API BACKOFFICE               ==================
    # =========================================================================
    # Tutte le API richiedono autenticazione
    # 1) Prenotazioni
    @app.post("/api/reservations")
    @login_required
    def api_reservation_create():
        """
        Payload atteso (JSON):
        {
          "date":"YYYY-MM-DD", "time":"HH:MM",
          "name":"", "phone":"", "people":4,
          "status":"Confermata", "notes":""
        }
        """
        data = request.get_json(force=True, silent=False)
        try:
            when = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
            r = models.Reservation(
                restaurant_id=current_user.restaurant_id,
                when=when,
                customer_name=(data.get("name") or "").strip(),
                customer_phone=(data.get("phone") or "").strip(),
                party_size=int(data.get("people", 2)),
                status=(data.get("status") or "Confermata"),
                notes=(data.get("notes") or "").strip(),
            )
            db.session.add(r)
            db.session.commit()
            return jsonify(ok=True, id=r.id)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    # 2) Orari settimanali (stringhe tipo "12:00-15, 19:00-22:30")
    @app.put("/api/restaurant/hours")
    @login_required
    def api_hours_update():
        """
        Payload atteso:
        { "mon":"12:00-15, 19:00-22:30", "tue":"", "wed":"", "thu":"", "fri":"", "sat":"", "sun":"" }
        Giorno vuoto = chiuso
        """
        data = request.get_json(force=True, silent=False)
        try:
            rest = models.Restaurant.query.get_or_404(current_user.restaurant_id)
            for key in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
                setattr(rest, f"hours_{key}", (data.get(key) or "").strip())
            db.session.commit()
            return jsonify(ok=True)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    # 3) Giorni speciali (aperture/chiusure e finestre orarie)
    @app.post("/api/restaurant/special")
    @login_required
    def api_special_upsert():
        """
        Payload:
        { "date":"YYYY-MM-DD", "closed":true/false, "windows":"18:00-23:00, 12:00-15:00" }
        """
        data = request.get_json(force=True, silent=False)
        try:
            d = datetime.strptime(data["date"], "%Y-%m-%d").date()
            s = models.SpecialDay.query.filter_by(
                restaurant_id=current_user.restaurant_id, day=d
            ).first()
            if not s:
                s = models.SpecialDay(
                    restaurant_id=current_user.restaurant_id,
                    day=d,
                )
                db.session.add(s)
            s.is_closed = bool(data.get("closed", False))
            s.windows = (data.get("windows") or "").strip()
            db.session.commit()
            return jsonify(ok=True, id=s.id)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    @app.delete("/api/restaurant/special")
    @login_required
    def api_special_delete():
        # querystring: ?date=YYYY-MM-DD
        ds = request.args.get("date")
        try:
            d = datetime.strptime(ds, "%Y-%m-%d").date()
            s = models.SpecialDay.query.filter_by(
                restaurant_id=current_user.restaurant_id, day=d
            ).first()
            if s:
                db.session.delete(s)
                db.session.commit()
            return jsonify(ok=True)
        except Exception as e:
            db.session.rollback()
            return jsonify(ok=False, error=str(e)), 400

    return app


# WSGI entrypoint per gunicorn
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

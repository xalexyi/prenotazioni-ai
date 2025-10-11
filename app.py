import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, current_user, logout_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

# -----------------------------------------------------------------------------
# App & DB
# -----------------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///instance/app.db"  # fallback locale
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login_page"

    with app.app_context():
        from backend.models import Restaurant, User, OpeningHours, SpecialDay, Settings, MenuItem, Reservation
        db.create_all()
        _ensure_columns()  # crea colonne mancanti in modo idempotente
    _register_routes(app)
    return app

app = create_app()

@login_manager.user_loader
def load_user(user_id):
    from backend.models import User
    return User.query.get(int(user_id))

# -----------------------------------------------------------------------------
# Migrazioni minime "idempotenti" (Postgres supporta IF NOT EXISTS)
# -----------------------------------------------------------------------------
from sqlalchemy import text
def _ensure_columns():
    stmts = [
        # user.password_hash
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password_hash TEXT;',
        # settings estese per prezzi fascia pranzo/cena e coperto/capienza/min persone
        'ALTER TABLE settings ADD COLUMN IF NOT EXISTS avg_price_lunch NUMERIC;',
        'ALTER TABLE settings ADD COLUMN IF NOT EXISTS avg_price_dinner NUMERIC;',
        'ALTER TABLE settings ADD COLUMN IF NOT EXISTS cover_fee NUMERIC;',
        'ALTER TABLE settings ADD COLUMN IF NOT EXISTS seats_cap INTEGER;',
        'ALTER TABLE settings ADD COLUMN IF NOT EXISTS min_people INTEGER;',
        # menu_item
        '''
        CREATE TABLE IF NOT EXISTS menu_item (
            id SERIAL PRIMARY KEY,
            restaurant_id INTEGER REFERENCES restaurant(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            price NUMERIC NOT NULL DEFAULT 0
        );
        '''
    ]
    for s in stmts:
        try:
            db.session.execute(text(s))
            db.session.commit()
        except Exception:
            db.session.rollback()

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
def _register_routes(app: Flask):

    from backend.models import Restaurant, User, OpeningHours, SpecialDay, Settings, MenuItem, Reservation

    # ------------------ AUTH ------------------
    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        msg = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            user = User.query.filter_by(username=username).first()
            if user and user.password_hash and check_password_hash(user.password_hash, password):
                login_user(user, remember=bool(request.form.get("remember")))
                return redirect(url_for("dashboard"))
            msg = "Credenziali non valide."
        return render_template("login.html", message=msg)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login_page"))

    # ------------------ DASHBOARD ------------------
    @app.route("/")
    @login_required
    def root():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    # ------------------ API: prenotazioni (lista/crea) ------------------
    @app.get("/api/reservations")
    @login_required
    def api_res_list():
        d = request.args.get("date")
        q = Reservation.query
        if d:
            q = q.filter_by(date=d)
        rows = [{
            "id": r.id,
            "name": r.name,
            "phone": r.phone,
            "people": r.people,
            "status": r.status,
            "date": r.date,
            "time": r.time,
        } for r in q.order_by(Reservation.time.asc()).all()]
        return jsonify(rows)

    @app.post("/api/reservations")
    @login_required
    def api_res_create():
        data = request.get_json(force=True)
        r = Reservation(
            restaurant_id=1,
            name=data["name"],
            phone=data.get("phone",""),
            people=int(data.get("people", 2)),
            status=data.get("status","Confermata"),
            note=data.get("note",""),
            date=data["date"],
            time=data["time"]
        )
        db.session.add(r)
        db.session.commit()
        return jsonify({"ok": True, "id": r.id})

    # ------------------ API: orari settimanali ------------------
    @app.get("/api/weekly-hours")
    @login_required
    def api_weekly_get():
        rows = OpeningHours.query.order_by(OpeningHours.weekday.asc()).all()
        mp = {}
        for r in rows:
            mp.setdefault(r.weekday, []).append(f"{r.start_time}-{r.end_time}")
        # torna array 0..6 con stringhe tipo "12:00-15:00, 19:00-22:30"
        out = []
        for dow in range(7):
            out.append(", ".join(mp.get(dow, [])))
        return jsonify(out)

    @app.post("/api/weekly-hours")
    @login_required
    def api_weekly_save():
        arr = request.get_json(force=True)  # array 7 stringhe
        # pulizia tabella e inserimento nuovo schema
        OpeningHours.query.delete()
        db.session.commit()
        for dow, s in enumerate(arr):
            s = (s or "").strip()
            if not s:
                continue
            for win in s.split(","):
                win = win.strip()
                if not win:
                    continue
                try:
                    a,b = [x.strip() for x in win.split("-")]
                except ValueError:
                    continue
                row = OpeningHours(restaurant_id=1, weekday=dow, start_time=a, end_time=b)
                db.session.add(row)
        db.session.commit()
        return jsonify({"ok": True})

    # ------------------ API: giorni speciali ------------------
    @app.get("/api/special-days")
    @login_required
    def api_special_list():
        rows = SpecialDay.query.order_by(SpecialDay.date.asc()).all()
        out = [{"date": r.date, "closed": r.closed, "windows": r.windows or ""} for r in rows]
        return jsonify(out)

    @app.post("/api/special-days")
    @login_required
    def api_special_upsert():
        data = request.get_json(force=True)
        d = data["date"]
        row = SpecialDay.query.filter_by(date=d).first()
        if not row:
            row = SpecialDay(restaurant_id=1, date=d)
            db.session.add(row)
        row.closed = bool(data.get("closed", False))
        row.windows = (data.get("windows") or "").strip()
        db.session.commit()
        return jsonify({"ok": True})

    @app.delete("/api/special-days/<d>")
    @login_required
    def api_special_delete(d):
        SpecialDay.query.filter_by(date=d).delete()
        db.session.commit()
        return jsonify({"ok": True})

    # ------------------ API: impostazioni / prezzi & coperti ------------------
    def _get_settings():
        s = Settings.query.filter_by(restaurant_id=1).first()
        if not s:
            s = Settings(restaurant_id=1)
            db.session.add(s)
            db.session.commit()
        return s

    @app.get("/api/settings/prices")
    @login_required
    def api_prices_get():
        s = _get_settings()
        return jsonify({
            "avg_price_lunch": s.avg_price_lunch or 0,
            "avg_price_dinner": s.avg_price_dinner or 0,
            "cover_fee": s.cover_fee or 0,
            "seats_cap": s.seats_cap or None,
            "min_people": s.min_people or None,
        })

    @app.post("/api/settings/prices")
    @login_required
    def api_prices_save():
        data = request.get_json(force=True)
        s = _get_settings()
        s.avg_price_lunch = data.get("avg_price_lunch") or 0
        s.avg_price_dinner = data.get("avg_price_dinner") or 0
        s.cover_fee = data.get("cover_fee") or 0
        s.seats_cap = data.get("seats_cap")
        s.min_people = data.get("min_people")
        db.session.commit()
        return jsonify({"ok": True})

    # ------------------ API: menu digitale (CRUD semplice) ------------------
    @app.get("/api/menu-items")
    @login_required
    def api_menu_list():
        rows = MenuItem.query.filter_by(restaurant_id=1).order_by(MenuItem.id.asc()).all()
        return jsonify([{"id":r.id,"name":r.name,"price":float(r.price)} for r in rows])

    @app.post("/api/menu-items")
    @login_required
    def api_menu_add():
        data = request.get_json(force=True)
        m = MenuItem(restaurant_id=1, name=data["name"].strip(), price=float(data.get("price",0)))
        db.session.add(m)
        db.session.commit()
        return jsonify({"ok": True, "id": m.id})

    @app.put("/api/menu-items/<int:item_id>")
    @login_required
    def api_menu_update(item_id):
        data = request.get_json(force=True)
        m = MenuItem.query.get_or_404(item_id)
        m.name = data.get("name", m.name).strip()
        m.price = float(data.get("price", m.price))
        db.session.commit()
        return jsonify({"ok": True})

    @app.delete("/api/menu-items/<int:item_id>")
    @login_required
    def api_menu_delete(item_id):
        MenuItem.query.filter_by(id=item_id).delete()
        db.session.commit()
        return jsonify({"ok": True})

# -----------------------------------------------------------------------------
# WSGI
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

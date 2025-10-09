# backend/admin_sql.py (USARE e poi rimuovere o proteggere)
from flask import Blueprint, jsonify
from sqlalchemy import text

try:
    from backend import db
except Exception:
    from app import db

bp_admin_sql = Blueprint("admin_sql", __name__)

@bp_admin_sql.route("/admin/sql/init-active-calls")
def init_active_calls():
    sql = open("sql/2025-10-active-calls.sql", "r", encoding="utf-8").read()
    with db.engine.begin() as conn:
        conn.execute(text(sql))
    return jsonify(ok=True)

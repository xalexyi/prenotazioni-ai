# backend/root.py
from flask import Blueprint, redirect, url_for, jsonify

# Il blueprint deve chiamarsi "bp" perché __init__.py lo importa così.
bp = Blueprint("root", __name__)

@bp.route("/")
def root_index():
    # Reindirizza alla pagina di login (blueprint "auth")
    return redirect(url_for("auth.login"))

@bp.route("/health")
def health():
    # Endpoint di healthcheck per Render
    return jsonify(status="ok")

"""
Backend package bootstrap.

Nota: teniamo questo file volutamente leggero per evitare import circolari.
I modelli sono in `backend.models`. Le utility/CLI sono in `backend.admin_sql`
e helper opzionali in `backend.monolith`.
"""

__all__ = ["models"]
__version__ = "1.0.0"

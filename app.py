# app.py
from backend import create_app
import os

app = create_app()

if __name__ == "__main__":
    # In locale avvia il server con host visibile in rete e porta configurabile
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)

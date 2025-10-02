# -*- coding: utf-8 -*-
# app.py — entrypoint dell’app Flask

from backend import create_app

app = create_app()

if __name__ == "__main__":
    # Avvio locale (in produzione usa il WSGI del provider)
    app.run(host="0.0.0.0", port=5000, debug=True)

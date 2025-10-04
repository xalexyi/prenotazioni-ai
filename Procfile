web: flask --app app.py db upgrade || true && gunicorn -w 2 -k gthread -t 120 "app:app"

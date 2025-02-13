#!/bin/sh
python ProductAnalyzer/manage.py collectstatic --noinpu
# Start Gunicorn
exec gunicorn SlackChatbot.wsgi:application --bind 0.0.0.0:8000 --workers=4 --timeout=3600

exec "$@"
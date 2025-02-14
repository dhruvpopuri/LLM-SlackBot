#!/bin/sh
if [ "$DATABASE" = "postgres" ]; then
    echo "Waiting for postgres..."

    while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

python manage.py collectstatic --noinpu
# Start Gunicorn
exec gunicorn SlackChatbot.wsgi:application --bind 0.0.0.0:8000 --workers=4 --timeout=3600

exec "$@"
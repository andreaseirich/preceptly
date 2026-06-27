#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate --noinput

if [ "${DEBUG:-True}" != "True" ] && [ "${DEBUG:-True}" != "true" ]; then
  python manage.py collectstatic --noinput
fi

# Daphne (ASGI) statt Gunicorn (WSGI) – WebSockets benötigen ASGI
exec daphne -b 0.0.0.0 -p ${PORT:-8000} --ping-interval 20 --ping-timeout 10 tutorflow.asgi:application

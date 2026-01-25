#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

python manage.py migrate --noinput

if [ "${DEBUG:-True}" != "True" ] && [ "${DEBUG:-True}" != "true" ]; then
  python manage.py collectstatic --noinput
fi

exec gunicorn tutorflow.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 4

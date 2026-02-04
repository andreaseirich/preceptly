#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Ensure Django is available
if ! python -c "import django" 2>/dev/null; then
  echo "Django not found. Run: pip install -r requirements.txt"
  exit 1
fi

# Ensure .env exists for reproducibility (copy from .env.example if missing)
if [ ! -f "${ROOT_DIR}/.env" ]; then
    if [ -f "${ROOT_DIR}/.env.example" ]; then
        cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
        echo "Created .env from .env.example"
    fi
fi

cd "${ROOT_DIR}/backend"

export MOCK_LLM="${MOCK_LLM:-1}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-tutorflow.settings}"

python manage.py migrate
python manage.py compilemessages
python manage.py load_demo_data

python manage.py runserver 0.0.0.0:8000


#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}/backend"

export MOCK_LLM="${MOCK_LLM:-1}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-tutorflow.settings}"

python manage.py migrate
python manage.py compilemessages

# Lösche Demo-User falls sie existieren, damit loaddata sie neu erstellen kann
python manage.py shell <<'PY'
from django.contrib.auth.models import User
from apps.core.models import UserProfile

# Lösche Demo-User falls vorhanden
for username in ["demo_premium", "demo_user"]:
    try:
        user = User.objects.get(username=username)
        # Lösche auch das zugehörige Profile
        if hasattr(user, 'profile'):
            user.profile.delete()
        user.delete()
        print(f"Deleted existing user: {username}")
    except User.DoesNotExist:
        pass
PY

# Lade Demo-Daten (inkl. Demo-User)
python manage.py loaddata fixtures/demo_data.json

# Stelle sicher, dass die Demo-User das richtige Passwort haben
python manage.py shell <<'PY'
from django.contrib.auth.models import User
from apps.core.models import UserProfile

def ensure_user(username, email, is_premium):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        print(f"Warning: User {username} not found after loaddata")
        return
    
    user.set_password("demo123")
    user.is_staff = True
    user.is_active = True
    user.save()
    
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.is_premium = is_premium
    profile.save()
    print(f"Updated user: {username} (premium: {is_premium})")

ensure_user("demo_premium", "demo_premium@example.com", True)
ensure_user("demo_user", "demo_user@example.com", False)
PY

python manage.py runserver 0.0.0.0:8000


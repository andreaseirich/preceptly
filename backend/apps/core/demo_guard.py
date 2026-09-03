"""
Missbrauchsschutz für öffentliche Demo-Konten (demo_premium / demo_user).

Demo-Accounts dürfen:
- Alle Features der jeweiligen Tier erkunden
- Eingeschränkt Daten anlegen (Limits pro Konto)

Demo-Accounts dürfen NICHT:
- Stripe Checkout starten
- KI unbegrenzt nutzen (Tageslimit)
- Passwort oder E-Mail-Adresse ändern

Alle Daten werden stündlich automatisch zurückgesetzt (Railway Cron).
"""

from django.core.cache import cache
from django.utils.translation import gettext as _

DEMO_USERNAMES: frozenset[str] = frozenset({"demo_premium", "demo_user"})

DEMO_CONTRACT_LIMIT = 8
DEMO_LESSON_LIMIT = 20
DEMO_AI_DAILY_LIMIT = 3


def is_demo_user(user) -> bool:
    return bool(
        user and getattr(user, "is_authenticated", False) and user.username in DEMO_USERNAMES
    )


def demo_block(request, message: str | None = None):
    """Redirect with error message for blocked demo actions."""
    from django.contrib import messages as msg
    from django.shortcuts import redirect
    from django.utils.http import url_has_allowed_host_and_scheme

    msg.error(
        request,
        message or _("This action is not available in demo mode."),
    )
    referer = request.META.get("HTTP_REFERER")
    # HTTP_REFERER is fully attacker-controlled - only follow it back if it
    # actually points at this site, otherwise fall back to the dashboard.
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(referer)
    return redirect("core:dashboard")


def demo_ai_limit_reached(user) -> bool:
    if not is_demo_user(user):
        return False
    count = cache.get(f"demo_ai:{user.pk}", 0)
    return count >= DEMO_AI_DAILY_LIMIT


def demo_ai_increment(user) -> int:
    key = f"demo_ai:{user.pk}"
    count = cache.get(key, 0) + 1
    cache.set(key, count, 86400)
    return count

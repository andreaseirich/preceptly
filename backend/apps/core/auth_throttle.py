"""
Simple rate limiting for login and register using Django cache.
Per-IP and per-username throttling; 429 on exceed.
"""

import hashlib
import time

from django.core.cache import cache
from django.shortcuts import render
from django.utils.translation import gettext as _


def _cache_key(prefix: str, value: str) -> str:
    """Build cache key; hash long values to avoid key length issues."""
    h = hashlib.sha256(value.encode()).hexdigest()[:16]
    return f"auth_throttle:{prefix}:{h}"


def _get_client_ip(request) -> str:
    """Lese die echte Client-IP, auch hinter einem Proxy (X-Forwarded-For)."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        ip = xff.split(",")[0].strip()[:64]
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")[:64]
    return ip or "unknown"


def _throttle_check(
    prefix: str,
    identifier: str,
    max_attempts: int = 5,
    window_seconds: int = 300,
) -> tuple[bool, int | None]:
    """
    Prüft, ob identifier das Limit überschritten hat.
    Gibt (allowed, retry_after_seconds) zurück.
    retry_after ist None wenn erlaubt.

    Atomare Implementierung über separate Integer-Keys (cache.add + cache.incr).
    """
    now = int(time.time())
    count_key = _cache_key(prefix, identifier) + ":count"
    meta_key = _cache_key(prefix, identifier) + ":meta"

    # Versuche, den Zähler neu anzulegen (nur wenn noch nicht vorhanden → atomar)
    added = cache.add(count_key, 1, timeout=window_seconds)
    if added:
        # Erster Aufruf im aktuellen Fenster
        cache.set(meta_key, {"window_start": now}, timeout=window_seconds)
        return (True, None)

    # Zähler existiert bereits – atomar inkrementieren
    try:
        count = cache.incr(count_key)
    except ValueError:
        # Zähler ist zwischenzeitlich abgelaufen; neu anlegen
        cache.add(count_key, 1, timeout=window_seconds)
        cache.set(meta_key, {"window_start": now}, timeout=window_seconds)
        return (True, None)

    # Fensterstartzeit ermitteln, um retry_after berechnen zu können
    meta = cache.get(meta_key) or {}
    window_start = meta.get("window_start", now)

    if count > max_attempts:
        retry = window_seconds - (now - window_start)
        return (False, max(1, retry))

    return (True, None)


def throttle_login(request):
    """
    Throttle Login-Versuche. Vor der Authentifizierung aufrufen.
    Gibt eine Response mit Status 429 zurück wenn gedrosselt, sonst None.
    """
    from django.contrib.auth.forms import AuthenticationForm

    ip = _get_client_ip(request)
    username = (
        (request.POST.get("username") or request.GET.get("username") or "").strip().lower()[:64]
    )

    allowed, retry = _throttle_check("login_ip", ip, max_attempts=10, window_seconds=300)
    if not allowed:
        response = render(
            request,
            "core/login.html",
            {
                "form": AuthenticationForm(request, data=request.POST if request.POST else None),
                "error": _("Too many attempts. Please try again later."),
                "show_landing_link": True,
            },
            status=429,
        )
        response["Retry-After"] = str(retry)
        return response

    if username:
        allowed, retry = _throttle_check("login_user", username, max_attempts=5, window_seconds=300)
        if not allowed:
            response = render(
                request,
                "core/login.html",
                {
                    "form": AuthenticationForm(
                        request, data=request.POST if request.POST else None
                    ),
                    "error": _("Too many attempts. Please try again later."),
                    "show_landing_link": True,
                },
                status=429,
            )
            response["Retry-After"] = str(retry)
            return response

    return None


def throttle_register(request):
    """
    Throttle Registrierungsversuche. Vor der Verarbeitung aufrufen.
    Gibt eine Response mit Status 429 zurück wenn gedrosselt, sonst None.
    """
    from apps.core.forms import RegisterForm

    ip = _get_client_ip(request)
    allowed, retry = _throttle_check("register_ip", ip, max_attempts=5, window_seconds=600)
    if not allowed:
        response = render(
            request,
            "core/register.html",
            {
                "form": RegisterForm(),
                "error": _("Too many registration attempts. Please try again later."),
            },
            status=429,
        )
        response["Retry-After"] = str(retry)
        return response

    return None

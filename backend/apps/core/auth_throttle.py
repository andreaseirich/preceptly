"""
Simple rate limiting for login and register using Django cache.
Per-IP and per-username throttling; 429 on exceed.
"""

import hashlib
import ipaddress
import logging
import time
import unicodedata

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def _cache_key(prefix: str, value: str) -> str:
    """Build cache key; hash long values to avoid key length issues."""
    h = hashlib.sha256(value.encode()).hexdigest()[:16]
    return f"auth_throttle:{prefix}:{h}"


def _is_trusted_proxy(ip: str, trusted: list) -> bool:
    """Return True if ip matches any entry in trusted (plain IP or CIDR range)."""
    for entry in trusted:
        if entry == ip:
            return True
        try:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            pass
    return False


def _get_client_ip(request) -> str:
    """Lese die echte Client-IP - nur wenn der Request durch einen bekannten
    Reverse-Proxy lief, wird X-Forwarded-For ausgewertet.

    TRUSTED_PROXIES unterstützt einzelne IPs und CIDR-Ranges (z.B. 10.0.0.0/8).

    Railway-spezifisches Mehrfach-Hop-Verhalten (empirisch verifiziert 2026-07-11):
    REMOTE_ADDR ist ein interner Railway-Proxy (100.64.0.0/10), X-Forwarded-For
    enthält [echte-Client-IP, weiterer-Railway-interner-Hop]. Da der rechteste Hop
    (152.233.12.241) selbst kein eintragbarer bekannter Proxy ist, würde der
    Right-most-untrusted-Algorithmus ihn fälschlich als Client-IP liefern.
    Stattdessen gilt: wenn REMOTE_ADDR vertrauenswürdig ist, ist die LINKESTE
    (erste) IP in X-Forwarded-For die echte Client-IP.
    """
    trusted_proxies = getattr(settings, "TRUSTED_PROXIES", [])
    remote = (request.META.get("REMOTE_ADDR") or "unknown")[:64]
    xff_raw = request.META.get("HTTP_X_FORWARDED_FOR", "")
    is_trusted = _is_trusted_proxy(remote, trusted_proxies)
    logger.debug(
        "[TRUSTED_PROXIES-DIAG] remote_addr=%s xff=%r trusted=%s", remote, xff_raw, is_trusted
    )
    if is_trusted and xff_raw:
        ips = [ip.strip() for ip in xff_raw.split(",") if ip.strip()]
        if ips:
            return ips[0][:64]
    return remote or "unknown"


def _throttle_check(
    prefix: str,
    identifier: str,
    max_attempts: int = 5,
    window_seconds: int = 300,
) -> tuple[bool, int | None]:
    """
    Prueft, ob identifier das Limit ueberschritten hat.
    Gibt (allowed, retry_after_seconds) zurueck.
    retry_after ist None wenn erlaubt.

    Atomare Implementierung ueber separate Integer-Keys (cache.add + cache.incr).
    """
    now = int(time.time())
    count_key = _cache_key(prefix, identifier) + ":count"
    meta_key = _cache_key(prefix, identifier) + ":meta"

    # Versuche, den Zaehler neu anzulegen (nur wenn noch nicht vorhanden -> atomar)
    added = cache.add(count_key, 1, timeout=window_seconds)
    if added:
        # Erster Aufruf im aktuellen Fenster
        cache.set(meta_key, {"window_start": now}, timeout=window_seconds)
        return (True, None)

    # Zaehler existiert bereits - atomar inkrementieren
    try:
        count = cache.incr(count_key)
    except ValueError:
        # Zaehler ist zwischenzeitlich abgelaufen; neu anlegen
        cache.add(count_key, 1, timeout=window_seconds)
        cache.set(meta_key, {"window_start": now}, timeout=window_seconds)
        return (True, None)

    # Fensterstartzeit ermitteln, um retry_after berechnen zu koennen
    meta = cache.get(meta_key) or {}
    window_start = meta.get("window_start", now)

    if count > max_attempts:
        retry = window_seconds - (now - window_start)
        return (False, max(1, retry))

    return (True, None)


def throttle_login(request):
    """
    Throttle Login-Versuche. Vor der Authentifizierung aufrufen.
    Gibt eine Response mit Status 429 zurueck wenn gedrosselt, sonst None.
    """
    from django.contrib.auth.forms import AuthenticationForm

    ip = _get_client_ip(request)

    # NKFC-Normalisierung + casefold verhindert Homoglyphen-/Casing-Bypass
    username_raw = (request.POST.get("username") or request.GET.get("username") or "").strip()
    username = unicodedata.normalize("NFKC", username_raw).casefold()[:64]

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

    # Demo-Konten: strengere Beschränkung (öffentliche Credentials)
    from apps.core.demo_guard import DEMO_USERNAMES

    if username in {u.casefold() for u in DEMO_USERNAMES}:
        allowed, retry = _throttle_check(
            "demo_login", username, max_attempts=20, window_seconds=3600
        )
        if not allowed:
            from django.contrib.auth.forms import AuthenticationForm as _AF

            response = render(
                request,
                "core/login.html",
                {
                    "form": _AF(request, data=request.POST if request.POST else None),
                    "error": _("Too many demo login attempts. Please try again later."),
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
    Gibt eine Response mit Status 429 zurueck wenn gedrosselt, sonst None.
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

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


def _throttle_check(
    prefix: str,
    identifier: str,
    max_attempts: int = 5,
    window_seconds: int = 300,
) -> tuple[bool, int | None]:
    """
    Check if identifier is over limit.
    Returns (allowed, retry_after_seconds).
    retry_after is None if allowed.
    """
    key = _cache_key(prefix, identifier)
    data = cache.get(key)
    now = int(time.time())
    if data is None:
        cache.set(key, {"count": 1, "window_start": now}, timeout=window_seconds)
        return (True, None)
    count = data.get("count", 0)
    window_start = data.get("window_start", now)
    if now - window_start >= window_seconds:
        # Window expired, reset
        cache.set(key, {"count": 1, "window_start": now}, timeout=window_seconds)
        return (True, None)
    if count >= max_attempts:
        retry = window_seconds - (now - window_start)
        return (False, max(1, retry))
    cache.set(
        key,
        {"count": count + 1, "window_start": window_start},
        timeout=window_seconds,
    )
    return (True, None)


def throttle_login(request):
    """
    Throttle login attempts. Call before authentication.
    Returns response with 429 if throttled, else None.
    """
    from django.contrib.auth.forms import AuthenticationForm

    ip = request.META.get("REMOTE_ADDR", "unknown")[:64]
    username = (request.POST.get("username") or request.GET.get("username") or "").strip()[:64]
    allowed, retry = _throttle_check("login_ip", ip, max_attempts=10, window_seconds=300)
    if not allowed:
        return render(
            request,
            "core/login.html",
            {
                "form": AuthenticationForm(request, data=request.POST if request.POST else None),
                "error": _("Too many attempts. Please try again later."),
                "show_landing_link": True,
            },
            status=429,
        )
    if username:
        allowed, retry = _throttle_check("login_user", username, max_attempts=5, window_seconds=300)
        if not allowed:
            return render(
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
    return None


def throttle_register(request):
    """
    Throttle register attempts. Call before processing.
    Returns response with 429 if throttled, else None.
    """
    from apps.core.forms import RegisterForm

    ip = request.META.get("REMOTE_ADDR", "unknown")[:64]
    allowed, retry = _throttle_check("register_ip", ip, max_attempts=5, window_seconds=600)
    if not allowed:
        form = RegisterForm()
        form.add_error(None, _("Too many registration attempts. Please try again later."))
        return render(
            request,
            "core/register.html",
            {"form": form},
            status=429,
        )
    return None

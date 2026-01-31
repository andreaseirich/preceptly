"""
Rate limiting for Public Booking APIs (brute-force protection).

Uses Django cache. Keys: IP and tutor_token.
Never log throttle keys or codes.
"""

from django.core.cache import cache

# Attempts per window
THROTTLE_IP_LIMIT = 15
THROTTLE_TUTOR_LIMIT = 8
THROTTLE_WINDOW_SECONDS = 900  # 15 minutes


def _get_client_ip(request) -> str:
    """Get client IP, considering X-Forwarded-For if behind proxy."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def is_public_booking_throttled(request, tutor_token: str | None = None) -> bool:
    """
    Check if request is rate-limited. Call before processing verify/search.

    Returns True if throttled (should reject), False if OK.
    """
    ip = _get_client_ip(request)
    ip_key = f"pb_throttle_ip:{ip}"
    ip_count = cache.get(ip_key, 0)
    if ip_count >= THROTTLE_IP_LIMIT:
        return True

    if tutor_token:
        tutor_key = f"pb_throttle_tutor:{tutor_token}"
        tutor_count = cache.get(tutor_key, 0)
        if tutor_count >= THROTTLE_TUTOR_LIMIT:
            return True

    return False


def record_public_booking_attempt(request, tutor_token: str | None = None) -> None:
    """Increment throttle counters. Call on each verify/search attempt."""
    ip = _get_client_ip(request)
    ip_key = f"pb_throttle_ip:{ip}"
    ip_count = cache.get(ip_key, 0) + 1
    cache.set(ip_key, ip_count, THROTTLE_WINDOW_SECONDS)

    if tutor_token:
        tutor_key = f"pb_throttle_tutor:{tutor_token}"
        tutor_count = cache.get(tutor_key, 0) + 1
        cache.set(tutor_key, tutor_count, THROTTLE_WINDOW_SECONDS)

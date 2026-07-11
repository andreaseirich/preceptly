import logging
import time

from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "testserver"}


class CanonicalDomainMiddleware:
    """Redirect www.preceptly.de and *.up.railway.app to https://preceptly.de (301)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DEBUG:
            raw = request.META.get("HTTP_HOST") or request.META.get("SERVER_NAME", "")
            host = raw.split(":")[0].lower()
            if host not in _LOCAL_HOSTS and (
                host == "www.preceptly.de" or host.endswith(".up.railway.app")
            ):
                return HttpResponsePermanentRedirect(
                    "https://preceptly.de" + request.get_full_path()
                )
        return self.get_response(request)


EXCLUDED_PATHS = (
    "/health/",
    "/static/",
    "/media/",
    "/favicon.ico",
    "/api/detect-timezone/",
    "/webhooks/",
    "/sw.js",
    "/manifest.json",
)


class RequestLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._rl_start = time.monotonic()

    def process_response(self, request, response):
        try:
            path = request.path
            if any(path.startswith(excl) for excl in EXCLUDED_PATHS):
                return response

            from apps.core.models import RequestLog  # noqa: PLC0415

            elapsed_ms = None
            if hasattr(request, "_rl_start"):
                elapsed_ms = int((time.monotonic() - request._rl_start) * 1000)

            xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
            if not ip:
                ip = None

            user = (
                request.user if hasattr(request, "user") and request.user.is_authenticated else None
            )
            session_key = ""
            if hasattr(request, "session") and request.session.session_key:
                session_key = request.session.session_key or ""

            RequestLog.objects.create(
                path=path[:500],
                method=request.method[:10],
                status_code=response.status_code,
                response_ms=elapsed_ms,
                user=user,
                session_key=session_key[:40],
                ip=ip,
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
                referer=request.META.get("HTTP_REFERER", "")[:500],
            )
        except Exception:
            logger.debug("RequestLog write failed", exc_info=True)
        return response

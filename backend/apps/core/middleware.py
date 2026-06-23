import time

from django.utils.deprecation import MiddlewareMixin

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
            pass
        return response

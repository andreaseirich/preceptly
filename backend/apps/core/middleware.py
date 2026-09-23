import hashlib
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect
from django.utils import timezone
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
    "/csp-report/",
)


DEFAULT_REQUEST_LOG_RETENTION_DAYS = 30
_PURGE_CACHE_KEY = "request_log_purged"
_PURGE_INTERVAL_SECONDS = 24 * 60 * 60


def purge_old_request_logs(retention_days=None):
    """Löscht Protokolleinträge, die älter sind als die Aufbewahrungsfrist."""
    from apps.core.models import RequestLog  # noqa: PLC0415

    if retention_days is None:
        retention_days = getattr(
            settings, "REQUEST_LOG_RETENTION_DAYS", DEFAULT_REQUEST_LOG_RETENTION_DAYS
        )
    cutoff = timezone.now() - timedelta(days=int(retention_days))
    deleted, _ = RequestLog.objects.filter(timestamp__lt=cutoff).delete()
    return deleted


def _pseudonymous_session_id(session_key):
    """Nur ein Kennzeichen zum Wiedererkennen - nie der Sitzungsschlüssel selbst.

    Der echte Schlüssel würde im Protokoll wie ein zweites Passwort liegen:
    Wer ihn liest, könnte die Sitzung übernehmen."""
    if not session_key:
        return ""
    return hashlib.sha256(session_key.encode()).hexdigest()[:40]


class RequestLogMiddleware(MiddlewareMixin):
    """Schreibt je Aufruf eine Zeile für die Zugriffsstatistik unter /dev/stats/.

    Statische Dateien, Webhooks und der Health-Check sind ausgenommen
    (siehe EXCLUDED_PATHS); Fehler beim Schreiben dürfen keine Antwort
    verhindern."""

    def process_request(self, request):
        request._rl_start = time.monotonic()

    def process_response(self, request, response):
        try:
            path = request.path
            if any(path.startswith(excl) for excl in EXCLUDED_PATHS):
                return response

            from apps.core.auth_throttle import _get_client_ip  # noqa: PLC0415
            from apps.core.models import RequestLog  # noqa: PLC0415

            elapsed_ms = None
            if hasattr(request, "_rl_start"):
                elapsed_ms = int((time.monotonic() - request._rl_start) * 1000)

            ip = _get_client_ip(request) or None

            user = (
                request.user if hasattr(request, "user") and request.user.is_authenticated else None
            )
            session_key = ""
            if hasattr(request, "session"):
                session_key = request.session.session_key or ""

            RequestLog.objects.create(
                path=path[:500],
                method=request.method[:10],
                status_code=response.status_code,
                response_ms=elapsed_ms,
                user=user,
                session_key=_pseudonymous_session_id(session_key),
                ip=ip,
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
                referer=request.META.get("HTTP_REFERER", "")[:500],
            )
            self._maybe_purge()
        except Exception:
            logger.debug("RequestLog write failed", exc_info=True)
        return response

    @staticmethod
    def _maybe_purge():
        """Einmal am Tag aufräumen - ohne Zeitplaner, also aus dem Betrieb heraus.

        ``cache.add`` setzt die Sperre nur, wenn sie noch nicht existiert;
        so löscht bei mehreren Prozessen trotzdem nur einer."""
        try:
            if not cache.add(_PURGE_CACHE_KEY, "1", _PURGE_INTERVAL_SECONDS):
                return
            deleted = purge_old_request_logs()
            if deleted:
                logger.info("RequestLog: %s alte Einträge gelöscht", deleted)
        except Exception:
            logger.debug("RequestLog purge failed", exc_info=True)

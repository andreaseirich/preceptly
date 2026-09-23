"""Sammelstelle für CSP-Verstöße.

Der Browser schickt hierher einen kleinen JSON-Bericht, sobald eine Seite gegen
die Richtlinie verstößt. Gleiche Verstöße werden nur einmal pro Stunde
protokolliert — sonst füllt ein einzelner Bot oder eine Browser-Erweiterung die
Logs.

Die Meldestelle ist offen erreichbar, der Inhalt der Berichte kommt also vom
Absender. Deshalb: Länge begrenzt, pro Stunde höchstens MAX_DISTINCT_PER_HOUR
verschiedene Meldungen im Cache — sonst könnte jemand mit erfundenen Berichten
den gemeinsamen Cache vollschreiben, in dem auch die Zähler der Rate-Limits
liegen."""

import json
import logging
from urllib.parse import urlsplit

from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

logger = logging.getLogger(__name__)

MAX_REPORT_BYTES = 8192
DEDUPE_SECONDS = 60 * 60
MAX_DISTINCT_PER_HOUR = 200
_COUNTER_KEY = "csp-report:distinct"


def _source_origin(value: str) -> str:
    """Nur Schema und Host - der Pfad macht sonst jeden Bericht einzigartig."""
    parts = urlsplit(value)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return value[:60]


def _should_log(directive: str, blocked: str) -> bool:
    key = f"csp-report:{directive[:40]}:{_source_origin(blocked)}"
    if not cache.add(key, "1", DEDUPE_SECONDS):
        return False
    try:
        cache.add(_COUNTER_KEY, 0, DEDUPE_SECONDS)
        distinct = cache.incr(_COUNTER_KEY)
    except ValueError:  # Zähler war zwischenzeitlich abgelaufen
        cache.set(_COUNTER_KEY, 1, DEDUPE_SECONDS)
        distinct = 1
    return distinct <= MAX_DISTINCT_PER_HOUR


@csrf_exempt
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def csp_report(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST erwartet")
    if len(request.body) > MAX_REPORT_BYTES:
        return HttpResponseBadRequest("Bericht zu groß")

    try:
        payload = json.loads(request.body.decode("utf-8", "replace"))
        report = payload.get("csp-report") or {}
    except (ValueError, AttributeError):
        return HttpResponseBadRequest("Kein gültiger Bericht")

    directive = str(report.get("effective-directive") or report.get("violated-directive") or "?")
    blocked = str(report.get("blocked-uri") or "?")
    document = str(report.get("document-uri") or "?")

    if _should_log(directive, blocked):
        logger.warning(
            "CSP-Verstoß: %s blockierte %s auf %s",
            directive[:100],
            blocked[:200],
            document[:200],
        )
    return HttpResponse(status=204)

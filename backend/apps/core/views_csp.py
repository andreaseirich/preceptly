"""Sammelstelle für CSP-Verstöße.

Der Browser schickt hierher einen kleinen JSON-Bericht, sobald eine Seite gegen
die Richtlinie verstößt. Gleiche Verstöße werden nur einmal pro Stunde
protokolliert — sonst füllt ein einzelner Bot oder eine Browser-Erweiterung die
Logs."""

import json
import logging

from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

logger = logging.getLogger(__name__)

MAX_REPORT_BYTES = 8192
DEDUPE_SECONDS = 60 * 60


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

    key = f"csp-report:{directive}:{blocked}"[:200]
    if cache.add(key, "1", DEDUPE_SECONDS):
        logger.warning(
            "CSP-Verstoß: %s blockierte %s auf %s",
            directive[:100],
            blocked[:200],
            document[:200],
        )
    return HttpResponse(status=204)

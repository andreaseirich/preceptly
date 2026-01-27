import logging
import sys

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_status(request):
    """Lightweight Health-Check-Endpunkt."""
    logger.info("Health check endpoint called")
    print("[HEALTH] Health check endpoint called", file=sys.stdout, flush=True)
    return JsonResponse({"status": "ok"})

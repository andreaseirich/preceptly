import logging

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_status(request):
    """Lightweight Health-Check-Endpunkt."""
    return JsonResponse({"status": "ok"})

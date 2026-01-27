"""
Simple test endpoint to verify logging works.
"""

import logging
import sys

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def test_logs(request):
    """
    Simple test endpoint that immediately outputs logs.
    Use this to verify that logging is working.
    """
    # Test logger
    logger.info("Test log from logger.info")
    logger.warning("Test log from logger.warning")
    logger.error("Test log from logger.error")

    # Test print to stdout
    print("[LOG_TEST] Test print to stdout", file=sys.stdout, flush=True)
    print("[LOG_TEST] Another test print", file=sys.stdout, flush=True)

    # Test print to stderr
    print("[LOG_TEST] Test print to stderr", file=sys.stderr, flush=True)

    return JsonResponse(
        {
            "success": True,
            "message": "Log test completed. Check server logs for output.",
            "logs_sent": [
                "logger.info",
                "logger.warning",
                "logger.error",
                "print to stdout (2x)",
                "print to stderr (1x)",
            ],
        }
    )

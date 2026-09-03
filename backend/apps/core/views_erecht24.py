"""Push webhook view for e-recht24 legal text updates."""

import json
import logging

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from apps.core.erecht24_service import handle_push

MAX_WEBHOOK_BYTES = 64 * 1024

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch")
class Erecht24PushView(View):
    """Receives push notifications from e-recht24 when legal texts change."""

    http_method_names = ["post"]

    def post(self, request):
        # Body-Größenbegrenzung: erst Content-Length-Header, dann echte Body-Länge prüfen
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length is not None:
            try:
                if int(content_length) > MAX_WEBHOOK_BYTES:
                    return JsonResponse({"code": 413, "message": "payload too large"}, status=413)
            except (ValueError, TypeError):
                # Malformed Content-Length header - fall through to the real
                # body-length check below instead of trusting the header.
                logger.debug("Malformed Content-Length header: %r", content_length)

        body = request.body
        if len(body) > MAX_WEBHOOK_BYTES:
            return JsonResponse({"code": 413, "message": "payload too large"}, status=413)

        content_type = request.content_type or ""
        if "application/json" in content_type:
            try:
                payload = json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return JsonResponse({"code": 400, "message": "invalid json"}, status=400)
            if not isinstance(payload, dict):
                return JsonResponse({"code": 400, "message": "invalid payload"}, status=400)
        else:
            payload = request.POST.dict()
            if not payload:
                payload = request.GET.dict()

        response = handle_push(payload)
        status = response.get("code", 200)
        return JsonResponse(response, status=status if status in (200, 400, 403) else 200)

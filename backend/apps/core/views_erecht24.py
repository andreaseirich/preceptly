"""Push webhook view for e-recht24 legal text updates."""

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.core.erecht24_service import handle_push

MAX_WEBHOOK_BYTES = 64 * 1024

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class Erecht24PushView(View):
    """Receives push notifications from e-recht24 when legal texts change."""

    http_method_names = ["post"]

    def post(self, request):
        secret = getattr(settings, "ERECHT24_PUSH_SECRET", None)
        if not secret:
            logger.error("ERECHT24_PUSH_SECRET not configured – rejecting push")
            return JsonResponse({"code": 403, "message": "invalid signature"}, status=403)

        # Body-Größenbegrenzung: erst Content-Length-Header, dann echte Body-Länge prüfen
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length is not None:
            try:
                if int(content_length) > MAX_WEBHOOK_BYTES:
                    return JsonResponse({"code": 413, "message": "payload too large"}, status=413)
            except (ValueError, TypeError):
                pass

        body = request.body
        if len(body) > MAX_WEBHOOK_BYTES:
            return JsonResponse({"code": 413, "message": "payload too large"}, status=413)

        signature = request.headers.get("X-ER24-Signature", "")
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("Erecht24 push rejected: invalid HMAC signature")
            return JsonResponse({"code": 403, "message": "invalid signature"}, status=403)

        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"code": 400, "message": "invalid json"}, status=400)

        if not isinstance(payload, dict):
            return JsonResponse({"code": 400, "message": "invalid payload"}, status=400)

        response = handle_push(payload)
        status = response.get("code", 200)
        return JsonResponse(response, status=status if status in (200, 400, 403) else 200)

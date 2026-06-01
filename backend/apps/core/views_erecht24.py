"""Push webhook view for e-recht24 legal text updates."""

import json
import logging

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.core.erecht24_service import handle_push

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class Erecht24PushView(View):
    """Receives push notifications from e-recht24 when legal texts change."""

    http_method_names = ["post"]

    def post(self, request):
        try:
            payload = json.loads(request.body.decode())
        except (ValueError, Exception):
            return JsonResponse({"code": 400, "message": "invalid json"}, status=400)

        response = handle_push(payload)
        status = response.get("code", 200)
        return JsonResponse(response, status=status if status in (200, 400, 403) else 200)

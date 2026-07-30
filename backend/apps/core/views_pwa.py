"""
Views for PWA (Progressive Web App) support.
"""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST


@cache_control(max_age=86400)  # Cache for 1 day
def manifest_view(request):
    """Serve the PWA manifest.json file."""
    manifest_path = Path(settings.BASE_DIR) / "apps" / "core" / "static" / "manifest.json"

    if not manifest_path.exists():
        raise Http404("Manifest file not found")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_content = f.read()

    return HttpResponse(manifest_content, content_type="application/manifest+json")


@cache_control(max_age=86400)  # Cache for 1 day
def service_worker_view(request):
    """Serve the service worker JavaScript file."""
    sw_path = Path(settings.BASE_DIR) / "apps" / "core" / "static" / "sw.js"

    if not sw_path.exists():
        raise Http404("Service worker file not found")

    with open(sw_path, "r", encoding="utf-8") as f:
        sw_content = f.read()

    return HttpResponse(sw_content, content_type="application/javascript")


@login_required
@require_POST
@csrf_protect
def push_subscribe_view(request):
    """POST body: {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}} - registers
    a Web Push subscription for the logged-in tutor."""
    from apps.core.push_service import save_push_subscription

    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        keys = data["keys"]
        p256dh = keys["p256dh"]
        auth = keys["auth"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return HttpResponseBadRequest("Invalid subscription payload")

    save_push_subscription(request.user, endpoint, p256dh, auth)
    return JsonResponse({"status": "ok"})


@login_required
@require_POST
@csrf_protect
def push_unsubscribe_view(request):
    """POST body: {"endpoint": ...} - removes a Web Push subscription for the
    logged-in tutor."""
    from apps.core.push_service import delete_push_subscription

    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return HttpResponseBadRequest("Invalid payload")

    delete_push_subscription(request.user, endpoint)
    return JsonResponse({"status": "ok"})

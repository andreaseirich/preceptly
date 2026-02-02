"""Project-level views (e.g. custom error handlers)."""

from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _


def custom_404(request, exception):
    """
    Custom 404 handler: returns JSON for API requests, HTML otherwise.
    Ensures we never raise 500 when template or i18n fails.
    """
    accept = request.META.get("HTTP_ACCEPT", "")
    if "application/json" in accept:
        return JsonResponse(
            {"error": "Not Found", "detail": _("The requested resource was not found.")},
            status=404,
        )
    try:
        return render(request, "404.html", status=404)
    except Exception:
        return HttpResponseNotFound(_("The page you are looking for does not exist."))

"""
Views for PWA (Progressive Web App) support.
"""

from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.cache import cache_control


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

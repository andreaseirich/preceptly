from django.conf import settings
from django.core.cache import cache

from apps.core.demo_guard import is_demo_user as _is_demo_user
from apps.portal.models import PortalMessage


def unread_portal_messages(request):
    if not request.user.is_authenticated:
        return {"unread_portal_count": 0}
    key = f"unread_portal:{request.user.pk}"
    count = cache.get(key)
    if count is None:
        count = PortalMessage.objects.filter(
            contract__user=request.user,
            read_by_tutor=False,
        ).count()
        cache.set(key, count, 30)
    return {"unread_portal_count": count}


def demo_context(request):
    return {"is_demo_user": _is_demo_user(request.user) if request.user.is_authenticated else False}


def vapid_public_key(request):
    """Exposes the (non-secret) VAPID public key to every template, for the
    push-notification subscribe flow. Empty string if push is not configured."""
    return {"vapid_public_key": getattr(settings, "VAPID_PUBLIC_KEY", "")}

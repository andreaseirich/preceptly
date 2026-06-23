from django.core.cache import cache

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


from apps.core.demo_guard import is_demo_user as _is_demo_user


def demo_context(request):
    return {"is_demo_user": _is_demo_user(request.user) if request.user.is_authenticated else False}

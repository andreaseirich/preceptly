from apps.portal.models import PortalMessage


def unread_portal_messages(request):
    if not request.user.is_authenticated:
        return {"unread_portal_count": 0}
    count = PortalMessage.objects.filter(
        student__user=request.user,
        read_by_tutor=False,
    ).count()
    return {"unread_portal_count": count}

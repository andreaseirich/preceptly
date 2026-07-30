"""
Web Push notification sending, gated by per-user NotificationPreference.

Notification types this service knows about must have matching
notify_<type>_email / notify_<type>_push fields on NotificationPreference.
"""

import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)


def is_channel_enabled(user, notification_type: str, channel: str) -> bool:
    """True if `user` wants `notification_type` delivered via `channel`
    ('email' or 'push'). No preference row yet => True, preserving today's
    always-on-email behavior for users who have never touched their settings."""
    from apps.core.models import NotificationPreference

    field = f"notify_{notification_type}_{channel}"
    pref = NotificationPreference.objects.filter(user=user).first()
    if pref is None:
        return True
    return getattr(pref, field, True)


def send_push_notification(
    user, notification_type: str, title: str, body: str, url: str | None = None
) -> int:
    """Send a Web Push notification to all of `user`'s registered devices,
    if push is enabled for `notification_type`. Returns how many devices
    were successfully notified (0 if push is off, unconfigured, or the user
    has no active subscriptions)."""
    if not is_channel_enabled(user, notification_type, "push"):
        return 0

    vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    vapid_public_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
    if not (vapid_private_key and vapid_public_key):
        logger.debug("VAPID keys not configured; skipping push for user %s", user.pk)
        return 0

    from apps.core.models import PushSubscription

    subscriptions = list(PushSubscription.objects.filter(user=user))
    if not subscriptions:
        return 0

    vapid_admin_email = getattr(settings, "VAPID_ADMIN_EMAIL", "")
    vapid_claims = {"sub": f"mailto:{vapid_admin_email}"} if vapid_admin_email else {}
    payload = json.dumps({"title": title, "body": body, "url": url or "/"})

    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=dict(vapid_claims),
            )
            sent += 1
        except WebPushException as e:
            status_code = getattr(e.response, "status_code", None)
            if status_code in (404, 410):
                sub.delete()
            else:
                logger.warning("Push send failed for user %s: %s", user.pk, e)
    return sent


def save_push_subscription(user, endpoint: str, p256dh: str, auth: str) -> None:
    """Create or update a PushSubscription for `user` from a
    PushSubscriptionJSON object's serialized fields."""
    from apps.core.models import PushSubscription

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": user, "p256dh": p256dh, "auth": auth},
    )


def delete_push_subscription(user, endpoint: str) -> None:
    """Remove a PushSubscription for `user`, if it exists."""
    from apps.core.models import PushSubscription

    PushSubscription.objects.filter(user=user, endpoint=endpoint).delete()

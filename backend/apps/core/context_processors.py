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


def account_email_context(request):
    """Tutor-Konto ohne E-Mail-Adresse bzw. mit unbestätigter - base.html zeigt
    dann einen Hinweis."""
    from apps.core.views_account_email import needs_email, needs_email_verification

    user = getattr(request, "user", None)
    missing = needs_email(user)
    return {
        "needs_email": missing,
        "needs_email_verification": not missing and needs_email_verification(user),
    }


def vapid_public_key(request):
    """Exposes the (non-secret) VAPID public key to every template, for the
    push-notification subscribe flow. Empty string if push is not configured."""
    return {"vapid_public_key": getattr(settings, "VAPID_PUBLIC_KEY", "")}


def csp_nonce(request):
    """Nonce der Content-Security-Policy für <script nonce="{{ csp_nonce }}">.

    Gesetzt von ContentSecurityPolicyMiddleware; ohne sie (etwa beim Rendern
    von E-Mails) bleibt der Wert leer."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}


def plan_features(request):
    """Welche tarifabhängigen Funktionen der angemeldete Tutor hat - für Vorlagen,
    damit sie Knöpfe nur zeigen, wenn die Aktion auch erlaubt ist."""
    from apps.core.feature_flags import Feature, user_has_feature

    user = getattr(request, "user", None)
    return {
        "plan": {
            "recurring": user_has_feature(user, Feature.FEATURE_RECURRING_LESSONS),
            "blocked_times": user_has_feature(user, Feature.FEATURE_BLOCKED_TIMES),
            "student_portal": user_has_feature(user, Feature.FEATURE_STUDENT_PORTAL),
            "family_access": user_has_feature(user, Feature.FEATURE_PARENT_PORTAL),
            "meetings": user_has_feature(user, Feature.FEATURE_MEETING_ROOMS),
        }
    }

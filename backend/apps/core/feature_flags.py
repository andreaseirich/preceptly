"""
Centralized Premium feature gating.

Features are granted based on user's premium status.
Basic: minimal features (students, contracts, lessons, calendar, basic billing).
Premium: full access including public booking (unlimited), reschedule, reports, billing-pro, AI.
"""

from enum import StrEnum

from django.contrib.auth.models import User


class Feature(StrEnum):
    """Feature keys for gating."""

    # Public Booking: Basic has limits (e.g. 10/month), Premium unlimited
    FEATURE_PUBLIC_BOOKING_FULL = "public_booking_full"

    # Public reschedule: Basic disabled, Premium enabled
    FEATURE_PUBLIC_RESCHEDULE = "public_reschedule"

    # Public series reschedule: Basic disabled, Premium enabled
    FEATURE_PUBLIC_SERIES_RESCHEDULE = "public_series_reschedule"

    # Reports/Stats page: Basic teaser, Premium full
    FEATURE_REPORTS = "reports"

    # Billing Pro: sequential invoice numbering, advanced filters
    FEATURE_BILLING_PRO = "billing_pro"

    # AI lesson plans (already premium)
    FEATURE_AI_LESSON_PLANS = "ai_lesson_plans"


# Mapping: which features Basic has (False = Premium only)
_FEATURE_IS_PREMIUM_ONLY = {
    Feature.FEATURE_PUBLIC_BOOKING_FULL: True,  # Basic has limited booking
    Feature.FEATURE_PUBLIC_RESCHEDULE: True,
    Feature.FEATURE_PUBLIC_SERIES_RESCHEDULE: True,
    Feature.FEATURE_REPORTS: True,  # Basic gets teaser
    Feature.FEATURE_BILLING_PRO: True,
    Feature.FEATURE_AI_LESSON_PLANS: True,
}


def is_premium_user(user: User | None) -> bool:
    """Check if user has premium access. Compatible with existing utils.is_premium_user."""
    if not user or not user.is_authenticated:
        return False
    try:
        return bool(user.profile.is_premium)
    except AttributeError:
        from apps.core.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"is_premium": False})
        return bool(profile.is_premium)


def user_has_feature(user: User | None, feature: Feature) -> bool:
    """
    Check if user has access to the given feature.

    Basic: no premium-only features.
    Premium: all features.
    """
    if not user or not user.is_authenticated:
        return False

    if not _FEATURE_IS_PREMIUM_ONLY.get(feature, True):
        return True

    return is_premium_user(user)


# Basic tier limit: max public bookings per calendar month
PUBLIC_BOOKING_MONTHLY_LIMIT = 10


def get_public_booking_count_this_month(tutor: User | None) -> int:
    """Count lessons created via public booking this month for the tutor."""
    if not tutor or not tutor.is_authenticated:
        return 0
    from apps.lessons.models import Lesson
    from django.utils import timezone

    now = timezone.now()
    return Lesson.objects.filter(
        contract__student__user=tutor,
        created_via="public_booking",
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()


def public_booking_limit_reached(tutor: User | None) -> bool:
    """True if Basic user has reached monthly public booking limit."""
    if user_has_feature(tutor, Feature.FEATURE_PUBLIC_BOOKING_FULL):
        return False  # Premium: no limit
    return get_public_booking_count_this_month(tutor) >= PUBLIC_BOOKING_MONTHLY_LIMIT


def require_feature_json(user: User | None, feature: Feature, message: str | None = None):
    """
    For API views: returns (False, JsonResponse) if feature denied, else (True, None).
    Caller should return the JsonResponse when False.
    """
    from django.http import JsonResponse
    from django.utils.translation import gettext as _

    if user_has_feature(user, feature):
        return (True, None)

    default_msg = _("This feature requires Premium. Upgrade to access.")
    return (False, JsonResponse({"success": False, "message": message or default_msg}, status=403))

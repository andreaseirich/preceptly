"""
Centralized feature gating for the 3-tier subscription system.

Tiers (ascending): free → starter → pro → business

Feature access is determined by subscription_tier on UserProfile.
"""

from enum import StrEnum

from django.contrib.auth.models import User


class Tier(StrEnum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"


TIER_RANK: dict[Tier, int] = {
    Tier.FREE: 0,
    Tier.STARTER: 1,
    Tier.PRO: 2,
    Tier.BUSINESS: 3,
}


class Feature(StrEnum):
    # Starter+ features
    FEATURE_RECURRING_LESSONS = "recurring_lessons"
    FEATURE_BLOCKED_TIMES = "blocked_times"
    FEATURE_DOCUMENTS = "documents"
    FEATURE_BILLING_PRO = "billing_pro"
    FEATURE_STUDENT_PORTAL = "student_portal"
    FEATURE_PORTAL_BOOKING = "portal_booking"

    # Pro+ features
    FEATURE_EUE_EXPORT = "eue_export"
    FEATURE_PARENT_PORTAL = "parent_portal"
    FEATURE_MEETING_ROOMS = "meeting_rooms"
    FEATURE_AI_LESSON_PLANS = "ai_lesson_plans"
    FEATURE_REPORTS = "reports"


FEATURE_MIN_TIER: dict[Feature, Tier] = {
    Feature.FEATURE_RECURRING_LESSONS: Tier.STARTER,
    Feature.FEATURE_BLOCKED_TIMES: Tier.STARTER,
    Feature.FEATURE_DOCUMENTS: Tier.STARTER,
    Feature.FEATURE_BILLING_PRO: Tier.STARTER,
    Feature.FEATURE_STUDENT_PORTAL: Tier.STARTER,
    Feature.FEATURE_PORTAL_BOOKING: Tier.STARTER,
    Feature.FEATURE_EUE_EXPORT: Tier.PRO,
    Feature.FEATURE_PARENT_PORTAL: Tier.PRO,
    Feature.FEATURE_MEETING_ROOMS: Tier.PRO,
    Feature.FEATURE_AI_LESSON_PLANS: Tier.PRO,
    Feature.FEATURE_REPORTS: Tier.PRO,
}

# Starter-tier limits
STARTER_DOCUMENT_LIMIT = 3
STARTER_PORTAL_BOOKING_MONTHLY_LIMIT = 3


def get_user_tier(user: User | None) -> Tier:
    """Return the subscription tier for a user."""
    if not user or not user.is_authenticated:
        return Tier.FREE
    try:
        tier_str = user.profile.subscription_tier
        return Tier(tier_str) if tier_str in Tier._value2member_map_ else Tier.FREE
    except AttributeError:
        from apps.core.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(
            user=user, defaults={"subscription_tier": "free"}
        )
        try:
            return Tier(profile.subscription_tier)
        except ValueError:
            return Tier.FREE


def user_has_feature(user: User | None, feature: Feature) -> bool:
    """Check if user has access to the given feature based on their tier."""
    if not user or not user.is_authenticated:
        return False
    min_tier = FEATURE_MIN_TIER.get(feature)
    if min_tier is None:
        return True
    return TIER_RANK[get_user_tier(user)] >= TIER_RANK[min_tier]


def is_premium_user(user: User | None) -> bool:
    """Backward-compat check: True for Pro and Business tiers."""
    return get_user_tier(user) in (Tier.PRO, Tier.BUSINESS)


def is_starter_or_above(user: User | None) -> bool:
    """True for Starter, Pro, and Business tiers."""
    return get_user_tier(user) != Tier.FREE


def get_document_count_for_contract(contract_id: int) -> int:
    """Count uploaded documents for a given contract/student."""
    from apps.students.models import StudentDocument

    return StudentDocument.objects.filter(student_id=contract_id).count()


def document_limit_reached(user: User | None, contract_id: int) -> bool:
    """True if Starter user has reached the document upload limit for this student."""
    if not user_has_feature(user, Feature.FEATURE_DOCUMENTS):
        return True
    if get_user_tier(user) == Tier.STARTER:
        return get_document_count_for_contract(contract_id) >= STARTER_DOCUMENT_LIMIT
    return False


def get_portal_booking_count_this_month(tutor: User | None) -> int:
    """Count portal bookings created this calendar month for the tutor."""
    if not tutor or not tutor.is_authenticated:
        return 0
    from django.utils import timezone

    from apps.lessons.models import Session

    now = timezone.now()
    return Session.objects.filter(
        contract__user=tutor,
        created_via="portal_booking",
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()


def portal_booking_limit_reached(tutor: User | None) -> bool:
    """True if Starter user has reached the monthly portal booking limit."""
    if not user_has_feature(tutor, Feature.FEATURE_PORTAL_BOOKING):
        return True
    if get_user_tier(tutor) == Tier.STARTER:
        return get_portal_booking_count_this_month(tutor) >= STARTER_PORTAL_BOOKING_MONTHLY_LIMIT
    return False


def require_feature_json(user: User | None, feature: Feature, message: str | None = None):
    """For API views: returns (False, JsonResponse) if feature denied, else (True, None)."""
    from django.http import JsonResponse
    from django.utils.translation import gettext as _

    if user_has_feature(user, feature):
        return (True, None)

    default_msg = _("This feature requires a higher subscription plan. Upgrade to access.")
    return (False, JsonResponse({"success": False, "message": message or default_msg}, status=403))

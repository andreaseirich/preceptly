"""
Stripe subscription utilities: user resolution, premium status rules.
"""

from apps.core.models import UserProfile

# Premium True only for these subscription statuses
PREMIUM_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing"})

# Premium False for these (no grace period)
NON_PREMIUM_SUBSCRIPTION_STATUSES = frozenset(
    {"past_due", "unpaid", "incomplete", "incomplete_expired", "canceled", "paused"}
)


def is_premium_subscription_status(status: str | None) -> bool:
    """Premium True only for active or trialing. All other statuses => False."""
    if not status:
        return False
    return status in PREMIUM_SUBSCRIPTION_STATUSES


def _extract_customer_id(obj: dict) -> str | None:
    """Extract customer ID from object (string or expanded dict)."""
    customer = obj.get("customer")
    if isinstance(customer, str) and customer.startswith("cus_"):
        return customer
    if isinstance(customer, dict):
        return customer.get("id")
    return None


def resolve_user_from_stripe_event(event: dict) -> UserProfile | None:
    """
    Resolve UserProfile from Stripe webhook event.
    1) metadata.user_id in event.data.object
    2) Fallback: stripe_customer_id -> UserProfile
    Returns None if no mapping found (webhook should return 200, no premium change).
    """
    data = event.get("data", {})
    obj = data.get("object", {})
    metadata = obj.get("metadata") or {}

    # 1) metadata.user_id
    user_id_str = metadata.get("user_id")
    if user_id_str:
        try:
            user_id = int(user_id_str)
            try:
                return UserProfile.objects.get(user_id=user_id)
            except UserProfile.DoesNotExist:
                return None
        except (ValueError, TypeError):
            pass

    # 2) Fallback: customer id -> UserProfile
    customer_id = _extract_customer_id(obj)
    if customer_id:
        return UserProfile.objects.filter(stripe_customer_id=customer_id).first()

    # 3) subscription id -> profile (for subscription.updated/deleted without metadata)
    sub_id = obj.get("id") or obj.get("subscription")
    if sub_id and isinstance(sub_id, str) and sub_id.startswith("sub_"):
        return UserProfile.objects.filter(stripe_subscription_id=sub_id).first()

    return None

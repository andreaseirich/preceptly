"""
Referral program: unique per-user codes, signup attribution, and the
"1 free month" reward credited to the referrer's Stripe balance once the
referred user's first real payment posts (see apps.core.views_stripe._handle_invoice_paid).
"""

import logging
import secrets
import string

import stripe
from django.db import transaction

from apps.core.models import UserProfile

logger = logging.getLogger(__name__)

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def ensure_referral_code(profile: UserProfile) -> str:
    """
    Ensures the UserProfile has a referral_code. Creates one if missing.
    Uses select_for_update() to prevent race conditions in concurrent requests.

    Returns:
        The (possibly newly generated) code
    """
    with transaction.atomic():
        locked = UserProfile.objects.select_for_update().get(pk=profile.pk)
        if not locked.referral_code:
            for _attempt in range(10):
                code = _generate_code()
                if not UserProfile.objects.filter(referral_code=code).exists():
                    locked.referral_code = code
                    locked.save(update_fields=["referral_code"])
                    break
            else:
                logger.error("Could not generate a unique referral_code after 10 attempts")
        return locked.referral_code


def resolve_referrer_user(code: str | None):
    """Return the User owning referral_code, or None if the code is missing/invalid."""
    if not code:
        return None
    profile = (
        UserProfile.objects.filter(referral_code=code.strip().upper())
        .select_related("user")
        .first()
    )
    return profile.user if profile else None


def _monthly_price_cents(price_id: str | None) -> int | None:
    """Fetch a Stripe Price's unit_amount in cents, or None if unavailable."""
    if not price_id:
        return None
    try:
        price = stripe.Price.retrieve(price_id)
        return price.get("unit_amount")
    except stripe.error.StripeError as e:
        logger.warning("Stripe Price.retrieve failed for %s: %s", price_id, e)
        return None


def apply_pending_referral_credit(profile: UserProfile) -> None:
    """
    If the referrer has pending free months and is a known Stripe customer with a
    known subscription price, apply the equivalent as a Stripe customer balance
    credit (negative balance = credit toward the next invoice) and clear the
    pending counter. No-op if the referrer isn't a paying Stripe customer yet
    (the pending count stays and is retried the next time this is called,
    e.g. at their own checkout).
    """
    if profile.referral_free_months_pending <= 0:
        return
    if not profile.stripe_customer_id or not profile.stripe_price_id:
        return

    unit_amount = _monthly_price_cents(profile.stripe_price_id)
    if not unit_amount:
        return

    credit_cents = unit_amount * profile.referral_free_months_pending

    try:
        customer = stripe.Customer.retrieve(profile.stripe_customer_id)
        current_balance = customer.get("balance", 0) or 0
        stripe.Customer.modify(
            profile.stripe_customer_id,
            balance=current_balance - credit_cents,
        )
    except stripe.error.StripeError as e:
        logger.warning(
            "Stripe balance credit failed for user=%s customer=%s: %s",
            profile.user_id,
            profile.stripe_customer_id,
            e,
        )
        return

    with transaction.atomic():
        locked = UserProfile.objects.select_for_update().get(pk=profile.pk)
        locked.referral_free_months_pending = 0
        locked.save(update_fields=["referral_free_months_pending"])

    logger.info(
        "Applied %s referral month(s) (%s cents) as Stripe balance credit for user=%s",
        credit_cents // unit_amount,
        credit_cents,
        profile.user_id,
    )


def grant_referral_reward_if_due(referred_profile: UserProfile) -> None:
    """
    Called when a referred user's invoice.paid fires with amount_paid > 0
    (their first real, non-trial payment). Grants the referrer one free month,
    exactly once per referred user (referral_reward_granted guards re-delivery
    of the webhook and later renewal invoices).
    """
    if not referred_profile.referred_by_id or referred_profile.referral_reward_granted:
        return

    with transaction.atomic():
        locked = UserProfile.objects.select_for_update().get(pk=referred_profile.pk)
        if locked.referral_reward_granted or not locked.referred_by_id:
            return
        locked.referral_reward_granted = True
        locked.save(update_fields=["referral_reward_granted"])

        referrer_profile = (
            UserProfile.objects.select_for_update().filter(user_id=locked.referred_by_id).first()
        )
        if not referrer_profile:
            return
        referrer_profile.referral_free_months_pending += 1
        referrer_profile.save(update_fields=["referral_free_months_pending"])

    logger.info(
        "Referral reward earned: referrer user=%s +1 free month (from referred user=%s)",
        referrer_profile.user_id,
        locked.user_id,
    )
    apply_pending_referral_credit(referrer_profile)

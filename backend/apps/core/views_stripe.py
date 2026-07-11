"""
Stripe subscription views: Checkout, Portal, Webhook.

Premium status is set ONLY via verified webhook events (source of truth).
"""

import logging
import time

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.demo_guard import demo_block, is_demo_user
from apps.core.models import StripeWebhookEvent, UserProfile
from apps.core.stripe_utils import (
    get_email_for_stripe,
    is_premium_subscription_status,
    resolve_user_from_stripe_event,
)

logger = logging.getLogger(__name__)

# Initialize Stripe API key once at module load time (not per-request)
if hasattr(settings, "STRIPE_SECRET_KEY") and settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _resolve_and_validate_profile(event, obj):
    """Resolve UserProfile from Stripe event with cross-validation against obj.customer."""
    profile = resolve_user_from_stripe_event(event)
    if not profile:
        return None
    event_customer_id = obj.get("customer")
    if event_customer_id and getattr(profile, "stripe_customer_id", None):
        if profile.stripe_customer_id != event_customer_id:
            logger.error(
                "SECURITY: customer_id mismatch profile=%s expected=%s got=%s",
                profile.pk,
                profile.stripe_customer_id,
                event_customer_id,
            )
            return None
    return profile


def _get_base_url(request: HttpRequest) -> str:
    """Return base URL. Prefer explicit SITE_BASE_URL; fall back to request (safe via ALLOWED_HOSTS)."""
    base = getattr(settings, "SITE_BASE_URL", None)
    if base:
        return base.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _safe_stripe_redirect(request, url):
    """Redirect only to validated stripe.com HTTPS URL."""
    from urllib.parse import urlparse

    from django.http import HttpResponseRedirect
    from django.urls import reverse

    if not url:
        messages.error(request, _("Could not start redirect. Please try again."))
        return HttpResponseRedirect(reverse("core:settings"))
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".stripe.com"):
        logger.warning("Blocked non-stripe redirect to %s", url)
        messages.error(request, _("Invalid redirect URL."))
        return HttpResponseRedirect(reverse("core:settings"))
    return HttpResponseRedirect(url)


def _stripe_enabled() -> bool:
    return getattr(settings, "STRIPE_ENABLED", False)


def _wants_json(request: HttpRequest) -> bool:
    """True if request expects JSON (AJAX/API)."""
    accept = (request.META.get("HTTP_ACCEPT") or "").lower()
    if "application/json" in accept:
        return True
    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        return True
    return False


def _stripe_checkout_error_response(request: HttpRequest) -> HttpResponse:
    """Return redirect (HTML) or 502 JSON for Stripe upstream failures."""
    msg = _("Could not start checkout. Please try again in a moment.")
    if _wants_json(request):
        return JsonResponse({"error": str(msg)}, status=502)
    messages.error(request, msg)
    return redirect(reverse("core:settings"), status=302)


def _active_subscription_guard(request: HttpRequest) -> HttpResponse | None:
    """
    Block checkout when the user already has an active subscription.

    Without this guard a second checkout (direct POST, second tab) creates a
    second Stripe subscription for the same customer: double billing, and the
    newer subscription ID overwrites the tracked one. Returns None if checkout
    may proceed, otherwise a response pointing the user to the billing portal
    (reachable from the settings page).
    """
    profile = UserProfile.objects.filter(user=request.user).first()
    if not profile:
        return None
    if profile.subscription_tier == "free" and not profile.stripe_subscription_id:
        return None
    logger.info(
        "Checkout blocked: user=%s already has an active subscription (tier=%s sub=%s)",
        request.user.id,
        profile.subscription_tier,
        profile.stripe_subscription_id,
    )
    msg = _(
        "You already have an active subscription. "
        "Please use the billing portal to manage or change your plan."
    )
    if _wants_json(request):
        return JsonResponse({"error": str(msg)}, status=409)
    messages.info(request, msg)
    return redirect(reverse("core:settings"))


@method_decorator(login_required, name="dispatch")
class SubscriptionCheckoutView(View):
    """POST: Create Stripe Checkout Session and redirect to Stripe."""

    http_method_names = ["post"]

    def post(self, request):
        if not request.POST.get("withdrawal_consent"):
            messages.error(request, _("Please confirm the withdrawal notice to proceed."))
            return redirect(reverse("core:settings"))

        if is_demo_user(request.user):
            return demo_block(request, _("Stripe checkout is not available in demo mode."))

        if not _stripe_enabled():
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        guard_response = _active_subscription_guard(request)
        if guard_response is not None:
            return guard_response

        tier_map = {
            "starter": getattr(settings, "STRIPE_PRICE_ID_STARTER", None),
            "pro": getattr(settings, "STRIPE_PRICE_ID_PRO", None)
            or getattr(settings, "STRIPE_PRICE_ID_MONTHLY", None),
            "business": getattr(settings, "STRIPE_PRICE_ID_BUSINESS", None),
        }
        requested_tier = request.POST.get("tier", "pro")
        price_id = tier_map.get(requested_tier) or getattr(
            settings, "STRIPE_PRICE_ID_MONTHLY", None
        )
        if not price_id:
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        user = request.user

        with transaction.atomic():
            profile, _created = UserProfile.objects.select_for_update().get_or_create(
                user=user, defaults={}
            )
            customer_id = profile.stripe_customer_id
            if not customer_id:
                try:
                    create_kw: dict = {
                        "metadata": {"user_id": str(user.id), "username": user.username}
                    }
                    email = get_email_for_stripe(user)
                    if email:
                        create_kw["email"] = email
                    customer = stripe.Customer.create(
                        **create_kw,
                        idempotency_key=f"customer:{user.id}",
                    )
                    customer_id = customer.id
                    profile.stripe_customer_id = customer_id
                    profile.save(update_fields=["stripe_customer_id"])
                except stripe.error.StripeError as e:
                    logger.warning(
                        "Stripe Customer.create failed user=%s status=%s code=%s",
                        user.id,
                        e.http_status,
                        getattr(e, "code", None),
                    )
                    return _stripe_checkout_error_response(request)

        base_url = _get_base_url(request)
        success_url = (
            getattr(settings, "STRIPE_CHECKOUT_SUCCESS_URL", None)
            or f"{base_url}{reverse('core:settings')}?checkout=success"
        )
        cancel_url = (
            getattr(settings, "STRIPE_CHECKOUT_CANCEL_URL", None)
            or f"{base_url}{reverse('core:settings')}?checkout=cancelled"
        )

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"user_id": str(user.id)},
                subscription_data={"metadata": {"user_id": str(user.id)}},
                idempotency_key=f"checkout:{user.id}:{int(time.time() // 60)}",
            )
        except stripe.error.StripeError as e:
            logger.warning(
                "Stripe checkout create failed user=%s status=%s code=%s",
                user.id,
                e.http_status,
                getattr(e, "code", None),
            )
            return _stripe_checkout_error_response(request)

        return _safe_stripe_redirect(request, session.url)


@method_decorator(login_required, name="dispatch")
class SubscriptionPortalView(View):
    """POST: Create Stripe Billing Portal Session and redirect."""

    http_method_names = ["post"]

    def post(self, request):
        if not _stripe_enabled():
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        profile = getattr(request.user, "profile", None)
        if not profile or not profile.stripe_customer_id:
            return redirect(reverse("core:settings"))

        _maybe_update_stripe_customer_email(profile, request.user)

        base_url = _get_base_url(request)
        return_url = (
            getattr(settings, "STRIPE_PORTAL_RETURN_URL", None)
            or f"{base_url}{reverse('core:settings')}"
        )

        try:
            session = stripe.billing_portal.Session.create(
                customer=profile.stripe_customer_id,
                return_url=return_url,
                idempotency_key=f"portal:{request.user.id}:{int(time.time() // 60)}",
            )
        except stripe.error.StripeError as e:
            logger.warning(
                "Stripe portal create failed user=%s status=%s code=%s",
                request.user.id,
                e.http_status,
                getattr(e, "code", None),
            )
            msg = _("Could not open billing portal. Please try again.")
            if _wants_json(request):
                return JsonResponse({"error": str(msg)}, status=502)
            messages.error(request, msg)
            return HttpResponseRedirect(reverse("core:settings"), status=302)

        return _safe_stripe_redirect(request, session.url)


def _stripe_premium_checkout_enabled() -> bool:
    """True if Stripe is configured for Premium checkout (STRIPE_PRICE_ID_MONTHLY)."""
    return getattr(settings, "STRIPE_PREMIUM_CHECKOUT_ENABLED", False)


def _maybe_update_stripe_customer_email(profile: UserProfile, user) -> None:
    """
    If user has valid email and Stripe customer exists but has no/different email, update via Customer.modify.
    No-op if email invalid, no stripe_customer_id, or already in sync.
    Never raises; errors are logged (no PII) and flow continues.
    """
    try:
        if not profile or not profile.stripe_customer_id:
            return
        new_email = get_email_for_stripe(user)
        if not new_email:
            return
        if profile.stripe_email_last_synced == new_email:
            return
        customer = stripe.Customer.retrieve(profile.stripe_customer_id)
        current = (customer.email or "").strip() or None
        if current == new_email:
            profile.stripe_email_last_synced = new_email
            profile.save(update_fields=["stripe_email_last_synced"])
            return
        stripe.Customer.modify(profile.stripe_customer_id, email=new_email)
        profile.stripe_email_last_synced = new_email
        profile.save(update_fields=["stripe_email_last_synced"])
    except stripe.error.StripeError as e:
        logger.warning("Stripe Customer email sync failed: %s %s", type(e).__name__, e.http_status)
    except Exception as e:
        logger.error("Stripe Customer email sync failed: %s", type(e).__name__)


@method_decorator(login_required, name="dispatch")
class StripeCheckoutView(View):
    """POST /stripe/checkout/: Create Stripe Checkout Session for subscription (STRIPE_PRICE_ID_MONTHLY)."""

    http_method_names = ["post"]

    def post(self, request):
        if not request.POST.get("withdrawal_consent"):
            messages.error(request, _("Please confirm the withdrawal notice to proceed."))
            return redirect(reverse("core:settings"))

        if is_demo_user(request.user):
            return demo_block(request, _("Stripe checkout is not available in demo mode."))

        if not _stripe_premium_checkout_enabled():
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        guard_response = _active_subscription_guard(request)
        if guard_response is not None:
            return guard_response

        tier_map = {
            "starter": getattr(settings, "STRIPE_PRICE_ID_STARTER", None),
            "pro": getattr(settings, "STRIPE_PRICE_ID_PRO", None)
            or getattr(settings, "STRIPE_PRICE_ID_MONTHLY", None),
            "business": getattr(settings, "STRIPE_PRICE_ID_BUSINESS", None),
        }
        requested_tier = request.POST.get("tier", "pro")
        price_id = tier_map.get(requested_tier) or getattr(
            settings, "STRIPE_PRICE_ID_MONTHLY", None
        )
        if not price_id:
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        user = request.user
        success_url = getattr(settings, "STRIPE_CHECKOUT_SUCCESS_URL", None) or (
            _get_base_url(request) + reverse("core:settings") + "?checkout=success"
        )
        cancel_url = getattr(settings, "STRIPE_CHECKOUT_CANCEL_URL", None) or (
            _get_base_url(request) + reverse("core:settings") + "?checkout=cancelled"
        )

        with transaction.atomic():
            profile, _created = UserProfile.objects.select_for_update().get_or_create(
                user=user, defaults={}
            )
            customer_id = profile.stripe_customer_id
            if not customer_id:
                try:
                    create_kw: dict = {"metadata": {"user_id": str(user.id)}}
                    email = get_email_for_stripe(user)
                    if email:
                        create_kw["email"] = email
                    customer = stripe.Customer.create(
                        **create_kw,
                        idempotency_key=f"customer:{user.id}",
                    )
                    customer_id = customer.id
                    profile.stripe_customer_id = customer_id
                    profile.save(update_fields=["stripe_customer_id"])
                except stripe.error.StripeError as e:
                    logger.warning(
                        "Stripe Customer.create failed user=%s status=%s code=%s",
                        user.id,
                        e.http_status,
                        getattr(e, "code", None),
                    )
                    return _stripe_checkout_error_response(request)
            else:
                _maybe_update_stripe_customer_email(profile, user)

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"user_id": str(user.id)},
                subscription_data={"metadata": {"user_id": str(user.id)}},
                idempotency_key=f"checkout:{user.id}:{int(time.time() // 60)}",
            )
        except stripe.error.StripeError as e:
            logger.warning(
                "Stripe checkout create failed user=%s status=%s code=%s",
                user.id,
                e.http_status,
                getattr(e, "code", None),
            )
            return _stripe_checkout_error_response(request)

        return _safe_stripe_redirect(request, session.url)


@method_decorator(login_required, name="dispatch")
class StripePortalView(View):
    """POST /stripe/portal/: Create Stripe Billing Portal Session. Requires stripe_customer_id."""

    http_method_names = ["post"]

    def post(self, request):
        if not _stripe_premium_checkout_enabled():
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        profile = getattr(request.user, "profile", None)
        if not profile or not profile.stripe_customer_id:
            return JsonResponse(
                {
                    "error": _(
                        "No billing customer found. Subscribe first to manage your subscription."
                    )
                },
                status=400,
            )

        _maybe_update_stripe_customer_email(profile, request.user)
        return_url = getattr(settings, "STRIPE_PORTAL_RETURN_URL", None) or (
            _get_base_url(request) + reverse("core:settings")
        )

        try:
            session = stripe.billing_portal.Session.create(
                customer=profile.stripe_customer_id,
                return_url=return_url,
                idempotency_key=f"portal:{request.user.id}:{int(time.time() // 60)}",
            )
        except stripe.error.StripeError as e:
            logger.warning(
                "Stripe portal create failed user=%s status=%s code=%s",
                request.user.id,
                e.http_status,
                getattr(e, "code", None),
            )
            msg = _("Could not open billing portal. Please try again.")
            return JsonResponse({"error": str(msg)}, status=502)

        return JsonResponse({"portal_url": session.url}, status=200)


@csrf_exempt
@require_POST
@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Handle Stripe webhooks. Verify signature, process events, update premium status.
    Source of truth: only webhook events set subscription_tier.
    """
    # [MEDIUM] Payload-Größenlimit gegen DoS
    if len(request.body) > 1024 * 64:
        return HttpResponseBadRequest("Payload too large")

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    if not webhook_secret:
        return HttpResponseBadRequest("Webhook secret not configured")

    try:
        # [MEDIUM] Expliziter tolerance-Parameter gegen Replay-Angriffe
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret, tolerance=300)
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")

    event_id = event.get("id")
    event_type = event.get("type")

    payload_summary = {"type": event_type}
    obj = event.get("data", {}).get("object", {})
    if obj.get("id"):
        payload_summary["object_id"] = str(obj["id"])[:50]

    # [MEDIUM] Webhook-Idempotenz: nur Events verwerfen, die bereits ERFOLGREICH
    # verarbeitet wurden (processed_at gesetzt). Eine Zeile ohne processed_at stammt
    # aus einem fehlgeschlagenen Versuch — der Stripe-Retry muss erneut verarbeiten.
    try:
        with transaction.atomic():
            webhook_event, created = StripeWebhookEvent.objects.get_or_create(
                event_id=event_id,
                defaults={"event_type": event_type, "payload_summary": payload_summary},
            )
            if not created and webhook_event.processed_at:
                return HttpResponse(status=200)
    except IntegrityError:
        # Race: anderer Worker hat denselben Event gerade eingefügt und verarbeitet ihn.
        # Schlägt er fehl, bleibt processed_at leer und der Stripe-Retry greift.
        return HttpResponse(status=200)

    try:
        _handle_stripe_event(event)
    except Exception as e:
        logger.exception(
            "Webhook handling failed type=%s event_id=%s err=%s",
            event_type,
            event_id,
            type(e).__name__,
        )
        # [MEDIUM] 500 zurückgeben damit Stripe den Event retryt (kein stilles Verwerfen);
        # processed_at bleibt leer, damit der Retry tatsächlich erneut verarbeitet.
        return HttpResponse(status=500)

    webhook_event.processed_at = timezone.now()
    webhook_event.save(update_fields=["processed_at"])
    return HttpResponse(status=200)


def _price_id_to_tier(price_id: str | None) -> str:
    """Map a Stripe price ID to a subscription tier string.

    Fail-closed: an unknown or missing price ID must never grant a paid tier.
    Unknown IDs indicate a tier-escalation attempt or a misconfiguration and
    are logged as an alert.
    """
    mapping = {
        getattr(settings, "STRIPE_PRICE_ID_STARTER", None): "starter",
        getattr(settings, "STRIPE_PRICE_ID_PRO", None): "pro",
        getattr(settings, "STRIPE_PRICE_ID_BUSINESS", None): "business",
        getattr(settings, "STRIPE_PRICE_ID_MONTHLY", None): "pro",
        getattr(settings, "STRIPE_PRICE_ID_YEARLY", None): "pro",
    }
    mapping.pop(None, None)  # unconfigured settings must not match price_id=None
    if price_id in mapping:
        return mapping[price_id]
    if price_id:
        logger.error(
            "ALERT: unknown Stripe price_id=%s — tier escalation attempt or "
            "misconfigured STRIPE_PRICE_ID_* settings; falling back to free",
            price_id,
        )
    else:
        logger.warning("No Stripe price_id available for tier mapping; falling back to free")
    return "free"


def _set_premium(profile: UserProfile, is_premium: bool, price_id: str | None = None) -> None:
    """Update profile premium status and subscription tier."""
    if is_premium:
        tier = _price_id_to_tier(price_id or profile.stripe_price_id)
        profile.subscription_tier = tier
        if not profile.premium_since:
            profile.premium_since = timezone.now()
    else:
        profile.subscription_tier = "free"
        profile.premium_since = None
    profile.subscription_source = "stripe" if is_premium else (profile.subscription_source or "")
    profile.save(update_fields=["subscription_tier", "premium_since", "subscription_source"])


def _handle_stripe_event(event: dict) -> None:
    """Process Stripe event and update UserProfile premium status. Unknown types -> no-op (200)."""
    event_type = event["type"]
    data = event.get("data", {})
    obj = data.get("object", {})

    if event_type == "checkout.session.completed":
        _handle_checkout_session_completed(event, obj)
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        _handle_subscription_created_or_updated(obj)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(obj)
    elif event_type == "invoice.payment_failed":
        _handle_invoice_payment_failed(obj)
    elif event_type == "invoice.paid":
        _handle_invoice_paid(obj)
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)


def _handle_checkout_session_completed(event: dict, session: dict) -> None:
    """Handle checkout.session.completed: capture customer+subscription, set premium from status."""
    profile = _resolve_and_validate_profile(event, session)
    if not profile:
        return

    sub_id = session.get("subscription")
    session_customer = session.get("customer")

    # Stripe API call OUTSIDE transaction (H11)
    sub_status = None
    if sub_id:
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            # [HIGH] Subscription muss zum selben Customer gehören wie die Session
            sub_customer = sub.get("customer")
            if sub_customer and session_customer and sub_customer != session_customer:
                logger.error(
                    "SECURITY: subscription customer mismatch sub=%s session=%s",
                    sub_customer,
                    session_customer,
                )
                return
            sub_status = sub.get("status", "")
        except stripe.error.StripeError as e:
            logger.warning(
                "Stripe Subscription.retrieve failed for %s status=%s code=%s",
                sub_id,
                e.http_status,
                getattr(e, "code", None),
            )

    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
        profile.stripe_customer_id = session_customer or profile.stripe_customer_id
        if sub_id:
            profile.stripe_subscription_id = sub_id
        profile.save(
            update_fields=[
                "stripe_customer_id",
                "stripe_subscription_id",
            ]
        )

        if sub_status is not None:
            _set_premium(profile, is_premium_subscription_status(sub_status))


def _handle_subscription_created_or_updated(subscription: dict) -> None:
    """Handle subscription.created/updated: update profile and premium from status."""
    from apps.core.stripe_utils import _extract_customer_id

    sub_id = subscription.get("id")
    customer_id = _extract_customer_id(subscription)
    status = subscription.get("status", "")
    is_premium = is_premium_subscription_status(status)

    synthetic_event = {"data": {"object": subscription}}
    profile = _resolve_and_validate_profile(synthetic_event, subscription)

    if not profile and customer_id:
        profile = UserProfile.objects.filter(stripe_customer_id=customer_id).first()
        # [HIGH] Ownership-Check: wenn das Profil bereits eine andere Subscription hat → Abbruch
        if profile and profile.stripe_subscription_id and profile.stripe_subscription_id != sub_id:
            logger.error(
                "SECURITY: subscription_id mismatch for customer=%s profile_sub=%s event_sub=%s",
                customer_id,
                profile.stripe_subscription_id,
                sub_id,
            )
            return

    if not profile and sub_id:
        profile = UserProfile.objects.filter(stripe_subscription_id=sub_id).first()

    if not profile:
        return

    # [MEDIUM] Price-ID gegen Whitelist prüfen
    price_id = None
    items_data = subscription.get("items") or {}
    items_list = items_data.get("data", []) if isinstance(items_data, dict) else []
    if items_list:
        first_item = items_list[0]
        price_obj = first_item.get("price")
        if isinstance(price_obj, dict):
            price_id = price_obj.get("id")
        elif isinstance(price_obj, str):
            price_id = price_obj

    allowed_prices = set(getattr(settings, "STRIPE_PREMIUM_PRICE_IDS", []))
    if price_id and allowed_prices and price_id not in allowed_prices:
        logger.warning(
            "Subscription with unknown price_id=%s user=%s — revoking premium",
            price_id,
            profile.pk,
        )
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
            _set_premium(profile, False)
        return

    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(pk=profile.pk)

        profile.stripe_subscription_id = sub_id
        profile.stripe_customer_id = customer_id or profile.stripe_customer_id

        if price_id:
            profile.stripe_price_id = price_id

        profile.save(
            update_fields=["stripe_subscription_id", "stripe_customer_id", "stripe_price_id"]
        )
        _set_premium(profile, is_premium)


def _handle_subscription_deleted(subscription: dict) -> None:
    """Handle subscription.deleted: clear subscription, set premium False."""
    sub_id = subscription.get("id")
    profile = UserProfile.objects.filter(stripe_subscription_id=sub_id).first()
    if profile:
        logger.warning(
            "subscription.deleted sub=%s user=%s",
            sub_id,
            profile.pk,
        )
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
            profile.stripe_subscription_id = None
            profile.stripe_price_id = None
            profile.save(update_fields=["stripe_subscription_id", "stripe_price_id"])
            _set_premium(profile, False)


def _handle_invoice_payment_failed(invoice: dict) -> None:
    """invoice.payment_failed: if subscription status implies non-premium, set premium False."""
    sub_id = invoice.get("subscription")
    if not sub_id:
        return
    profile = UserProfile.objects.filter(stripe_subscription_id=sub_id).first()
    if not profile:
        return

    # Cross-validate customer_id if present on invoice
    invoice_customer_id = invoice.get("customer")
    if invoice_customer_id and profile.stripe_customer_id:
        if profile.stripe_customer_id != invoice_customer_id:
            logger.error(
                "SECURITY: customer_id mismatch profile=%s expected=%s got=%s",
                profile.pk,
                profile.stripe_customer_id,
                invoice_customer_id,
            )
            return

    logger.warning(
        "invoice.payment_failed sub=%s user=%s",
        sub_id,
        profile.pk,
    )

    # Stripe API call OUTSIDE transaction
    try:
        sub = stripe.Subscription.retrieve(sub_id)
        status = sub.get("status", "")
    except stripe.error.StripeError as e:
        logger.warning("Stripe Subscription.retrieve failed for invoice: %s", e.http_status)
        # Re-raise: nichts wurde verarbeitet → Webhook antwortet 500 und Stripe retryt,
        # statt den Event stillschweigend als verarbeitet zu markieren.
        raise

    if not is_premium_subscription_status(status):
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
            _set_premium(profile, False)


def _handle_invoice_paid(invoice: dict) -> None:
    """invoice.paid: no premium toggle, ensure no errors."""
    pass

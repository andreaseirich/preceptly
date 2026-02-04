"""
Stripe subscription views: Checkout, Portal, Webhook.

Premium status is set ONLY via verified webhook events (source of truth).
"""

import logging

import stripe
from apps.core.models import StripeWebhookEvent, UserProfile
from apps.core.stripe_utils import is_premium_subscription_status, resolve_user_from_stripe_event
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _get_base_url(request: HttpRequest) -> str:
    """Build absolute base URL respecting X-Forwarded-Proto for Railway."""
    scheme = "https" if request.is_secure() else request.scheme
    if "HTTP_X_FORWARDED_PROTO" in request.META:
        scheme = request.META["HTTP_X_FORWARDED_PROTO"].split(",")[0].strip()
    host = request.get_host()
    return f"{scheme}://{host}"


def _stripe_enabled() -> bool:
    return getattr(settings, "STRIPE_ENABLED", False)


@method_decorator(login_required, name="dispatch")
class SubscriptionCheckoutView(View):
    """POST: Create Stripe Checkout Session and redirect to Stripe."""

    http_method_names = ["post"]

    def post(self, request):
        if not _stripe_enabled():
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        user = request.user
        profile, _created = UserProfile.objects.get_or_create(
            user=user, defaults={"is_premium": False}
        )

        base_url = _get_base_url(request)
        success_url = (
            settings.STRIPE_CHECKOUT_SUCCESS_URL
            or f"{base_url}{reverse('core:settings')}?checkout=success"
        )
        cancel_url = (
            settings.STRIPE_CHECKOUT_CANCEL_URL
            or f"{base_url}{reverse('core:settings')}?checkout=cancelled"
        )

        customer_id = profile.stripe_customer_id if profile else None
        if not customer_id:
            customer = stripe.Customer.create(
                email=user.email or f"{user.username}@placeholder.local",
                metadata={"user_id": str(user.id), "username": user.username},
            )
            customer_id = customer.id
            profile.stripe_customer_id = customer_id
            profile.save(update_fields=["stripe_customer_id"])

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[
                    {
                        "price": settings.STRIPE_PRICE_ID_MONTHLY,
                        "quantity": 1,
                    }
                ],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"user_id": str(user.id)},
                subscription_data={"metadata": {"user_id": str(user.id)}},
            )
        except stripe.error.StripeError as e:
            logger.warning("Stripe checkout create failed: %s", str(e)[:200])
            return JsonResponse(
                {"error": _("Could not create checkout session. Please try again.")}, status=500
            )

        return redirect(session.url, status=303)


@method_decorator(login_required, name="dispatch")
class SubscriptionPortalView(View):
    """POST: Create Stripe Billing Portal Session and redirect."""

    http_method_names = ["post"]

    def post(self, request):
        if not _stripe_enabled():
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.stripe_customer_id:
            return redirect(reverse("core:settings"))

        base_url = _get_base_url(request)
        return_url = settings.STRIPE_PORTAL_RETURN_URL or f"{base_url}{reverse('core:settings')}"

        try:
            session = stripe.billing_portal.Session.create(
                customer=profile.stripe_customer_id,
                return_url=return_url,
            )
        except stripe.error.StripeError as e:
            logger.warning("Stripe portal create failed: %s", str(e)[:200])
            return JsonResponse(
                {"error": _("Could not open billing portal. Please try again.")}, status=500
            )

        return redirect(session.url, status=303)


def _stripe_premium_checkout_enabled() -> bool:
    """True if Stripe is configured for Premium checkout (STRIPE_PRICE_ID_MONTHLY)."""
    return getattr(settings, "STRIPE_PREMIUM_CHECKOUT_ENABLED", False)


@method_decorator(login_required, name="dispatch")
class StripeCheckoutView(View):
    """POST /stripe/checkout/: Create Stripe Checkout Session for subscription (STRIPE_PRICE_ID_MONTHLY)."""

    http_method_names = ["post"]

    def post(self, request):
        if not _stripe_premium_checkout_enabled():
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        price_id = getattr(settings, "STRIPE_PRICE_ID_MONTHLY", None)
        if not price_id:
            return JsonResponse(
                {"error": _("Payment is not configured. Please contact support.")}, status=503
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        user = request.user
        success_url = getattr(
            settings, "STRIPE_CHECKOUT_SUCCESS_URL", None
        ) or request.build_absolute_uri(reverse("core:settings") + "?checkout=success")
        cancel_url = getattr(
            settings, "STRIPE_CHECKOUT_CANCEL_URL", None
        ) or request.build_absolute_uri(reverse("core:settings") + "?checkout=cancelled")

        with transaction.atomic():
            profile, _created = UserProfile.objects.select_for_update().get_or_create(
                user=user, defaults={"is_premium": False}
            )
            customer_id = profile.stripe_customer_id
            if not customer_id:
                customer = stripe.Customer.create(
                    email=user.email or f"{user.username}@placeholder.local",
                    metadata={"user_id": str(user.id), "username": user.username},
                )
                customer_id = customer.id
                profile.stripe_customer_id = customer_id
                profile.save(update_fields=["stripe_customer_id"])

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"user_id": str(user.id)},
                subscription_data={"metadata": {"user_id": str(user.id)}},
            )
        except stripe.error.StripeError as e:
            logger.warning("Stripe checkout create failed: %s", str(e)[:200])
            return JsonResponse(
                {"error": _("Could not create checkout session. Please try again.")}, status=500
            )

        return redirect(session.url, status=303)


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

        stripe.api_key = settings.STRIPE_SECRET_KEY
        return_url = getattr(
            settings, "STRIPE_PORTAL_RETURN_URL", None
        ) or request.build_absolute_uri(reverse("core:settings"))

        try:
            session = stripe.billing_portal.Session.create(
                customer=profile.stripe_customer_id,
                return_url=return_url,
            )
        except stripe.error.StripeError as e:
            logger.warning("Stripe portal create failed: %s", str(e)[:200])
            return JsonResponse(
                {"error": _("Could not open billing portal. Please try again.")}, status=500
            )

        return JsonResponse({"portal_url": session.url}, status=200)


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Handle Stripe webhooks. Verify signature, process events, update premium status.
    Source of truth: only webhook events set is_premium.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    if not webhook_secret:
        return HttpResponseBadRequest("Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
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

    try:
        with transaction.atomic():
            webhook_event, created = StripeWebhookEvent.objects.get_or_create(
                event_id=event_id,
                defaults={"event_type": event_type, "payload_summary": payload_summary},
            )
            if not created:
                return HttpResponse(status=200)
    except IntegrityError:
        return HttpResponse(status=200)  # Race: duplicate event_id

    try:
        _handle_stripe_event(event)
    except Exception as e:
        logger.exception("Webhook handling failed for %s: %s", event_type, e)
        return HttpResponse(status=200)  # 200 to avoid Stripe retries for logic errors

    return HttpResponse(status=200)


def _set_premium(profile: UserProfile, is_premium: bool) -> None:
    """Update profile premium status."""
    profile.is_premium = is_premium
    if is_premium and not profile.premium_since:
        profile.premium_since = timezone.now()
    if not is_premium:
        profile.premium_since = None
    profile.premium_source = "stripe" if is_premium else (profile.premium_source or "")
    profile.save(update_fields=["is_premium", "premium_since", "premium_source"])


def _handle_stripe_event(event: dict) -> None:
    """Process Stripe event and update UserProfile premium status. Unknown types -> no-op (200)."""
    stripe.api_key = settings.STRIPE_SECRET_KEY

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
    profile = resolve_user_from_stripe_event(event)
    if not profile:
        return

    profile.stripe_customer_id = session.get("customer") or profile.stripe_customer_id
    sub_id = session.get("subscription")
    if sub_id:
        profile.stripe_subscription_id = sub_id
    profile.save(update_fields=["stripe_customer_id", "stripe_subscription_id"])

    if sub_id:
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            status = sub.get("status", "")
            _set_premium(profile, is_premium_subscription_status(status))
        except stripe.error.StripeError as e:
            logger.warning("Stripe Subscription.retrieve failed for %s: %s", sub_id, str(e)[:100])


def _handle_subscription_created_or_updated(subscription: dict) -> None:
    """Handle subscription.created/updated: update profile and premium from status."""
    from apps.core.stripe_utils import _extract_customer_id

    sub_id = subscription.get("id")
    customer_id = _extract_customer_id(subscription)
    status = subscription.get("status", "")
    is_premium = is_premium_subscription_status(status)

    # Build synthetic event for resolve_user_from_stripe_event
    synthetic_event = {"data": {"object": subscription}}
    profile = resolve_user_from_stripe_event(synthetic_event)

    if not profile and customer_id:
        profile = UserProfile.objects.filter(stripe_customer_id=customer_id).first()
    if not profile and sub_id:
        profile = UserProfile.objects.filter(stripe_subscription_id=sub_id).first()
    if not profile:
        return

    profile.stripe_subscription_id = sub_id
    profile.stripe_customer_id = customer_id or profile.stripe_customer_id

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
    if price_id:
        profile.stripe_price_id = price_id

    profile.save(update_fields=["stripe_subscription_id", "stripe_customer_id", "stripe_price_id"])
    _set_premium(profile, is_premium)


def _handle_subscription_deleted(subscription: dict) -> None:
    """Handle subscription.deleted: clear subscription, set premium False."""
    sub_id = subscription.get("id")
    profile = UserProfile.objects.filter(stripe_subscription_id=sub_id).first()
    if profile:
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
    try:
        sub = stripe.Subscription.retrieve(sub_id)
        status = sub.get("status", "")
        if not is_premium_subscription_status(status):
            _set_premium(profile, False)
    except stripe.error.StripeError as e:
        logger.warning("Stripe Subscription.retrieve failed for invoice: %s", str(e)[:100])


def _handle_invoice_paid(invoice: dict) -> None:
    """invoice.paid: no premium toggle, ensure no errors."""
    pass

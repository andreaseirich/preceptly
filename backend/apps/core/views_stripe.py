"""
Stripe subscription views: Checkout, Portal, Webhook.

Premium status is set ONLY via verified webhook events (source of truth).
"""

import logging

import stripe
from apps.core.models import UserProfile
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
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

    # Idempotency: skip if already processed
    from apps.core.models import StripeWebhookEvent

    if StripeWebhookEvent.objects.filter(event_id=event_id).exists():
        return HttpResponse(status=200)

    payload_summary = {"type": event_type}
    if event.get("data", {}).get("object", {}).get("id"):
        payload_summary["object_id"] = event["data"]["object"]["id"][:50]

    StripeWebhookEvent.objects.create(
        event_id=event_id,
        event_type=event_type,
        payload_summary=payload_summary,
    )

    try:
        _handle_stripe_event(event)
    except Exception as e:
        logger.exception("Webhook handling failed for %s: %s", event_type, e)
        return HttpResponse(status=200)  # Return 200 to avoid Stripe retries for logic errors

    return HttpResponse(status=200)


def _handle_stripe_event(event):
    """Process Stripe event and update UserProfile premium status."""
    from django.utils import timezone

    stripe.api_key = settings.STRIPE_SECRET_KEY

    event_type = event["type"]
    data = event.get("data", {})
    obj = data.get("object", {})

    def _get_user_id_from_obj(o):
        uid = o.get("metadata", {}).get("user_id")
        if uid:
            return int(uid)
        subscription_id = o.get("id") or o.get("subscription")
        if subscription_id:
            profile = UserProfile.objects.filter(stripe_subscription_id=subscription_id).first()
            if profile:
                return profile.user_id
        customer_id = o.get("customer")
        if customer_id:
            if isinstance(customer_id, str) and customer_id.startswith("cus_"):
                profile = UserProfile.objects.filter(stripe_customer_id=customer_id).first()
                if profile:
                    return profile.user_id
        return None

    def _set_premium(profile, is_premium):
        profile.is_premium = is_premium
        if is_premium and not profile.premium_since:
            profile.premium_since = timezone.now()
        if not is_premium:
            profile.premium_since = None
        profile.premium_source = "stripe" if is_premium else profile.premium_source or ""
        profile.save(update_fields=["is_premium", "premium_since", "premium_source"])

    if event_type == "checkout.session.completed":
        session = obj
        user_id = int(session.get("metadata", {}).get("user_id", 0)) or _get_user_id_from_obj(
            session
        )
        if not user_id:
            return
        try:
            profile = UserProfile.objects.get(user_id=user_id)
        except UserProfile.DoesNotExist:
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
                _set_premium(profile, status in ("active", "trialing"))
            except stripe.error.StripeError:
                pass

    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        subscription = obj
        sub_id = subscription.get("id")
        customer_id = subscription.get("customer")
        status = subscription.get("status", "")
        is_premium = status in ("active", "trialing")

        profile = None
        user_id = _get_user_id_from_obj(subscription)
        if user_id:
            try:
                profile = UserProfile.objects.get(user_id=user_id)
            except UserProfile.DoesNotExist:
                pass
        if not profile and customer_id:
            profile = UserProfile.objects.filter(stripe_customer_id=customer_id).first()
        if not profile:
            return

        profile.stripe_subscription_id = sub_id
        profile.stripe_customer_id = customer_id or profile.stripe_customer_id
        price_id = None
        items_data = subscription.get("items") or {}
        if isinstance(items_data, dict):
            items_list = items_data.get("data") or []
        else:
            items_list = []
        if items_list:
            first_item = items_list[0]
            price_obj = first_item.get("price")
            if isinstance(price_obj, dict):
                price_id = price_obj.get("id")
            elif isinstance(price_obj, str):
                price_id = price_obj
        if price_id:
            profile.stripe_price_id = price_id
        profile.save(
            update_fields=["stripe_subscription_id", "stripe_customer_id", "stripe_price_id"]
        )
        _set_premium(profile, is_premium)

    elif event_type == "customer.subscription.deleted":
        subscription = obj
        sub_id = subscription.get("id")
        profile = UserProfile.objects.filter(stripe_subscription_id=sub_id).first()
        if profile:
            profile.stripe_subscription_id = None
            profile.stripe_price_id = None
            profile.save(update_fields=["stripe_subscription_id", "stripe_price_id"])
            _set_premium(profile, False)

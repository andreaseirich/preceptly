"""Webhook and confirmation views for the e-recht24 revocation button.

This is a SEPARATE protocol from the e-recht24 legal-text push webhook
(views_erecht24.py): the revocation button signs the raw request body with
HMAC-SHA256 and sends the result in the X-Webhook-Signature header
("sha256=<hex>"), while the push webhook carries a secret inside the payload
and sends no signature header. Different secrets, different purpose.

Security model: the e-recht24 revocation form is self-reported and NOT
identity-verified — anyone who knows a customer's email address could submit
a revocation for it. An incoming webhook therefore NEVER cancels a
subscription directly. It only records a RevocationRequest and emails a
confirmation link to the address stored on the matched account (user.email,
never the payload email). The Stripe cancellation happens only after the
account owner confirms via POST on the tokenized confirmation page.
"""

import logging
import re
from datetime import timedelta

import stripe
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from apps.core.models import RevocationRequest, UserProfile
from apps.core.views_stripe import _set_premium

CONFIRMATION_TOKEN_MAX_AGE = timedelta(days=14)  # gesetzliche Widerrufsfrist

logger = logging.getLogger(__name__)

if hasattr(settings, "STRIPE_SECRET_KEY") and settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _sanitize_for_subject(value: str, max_len: int = 100) -> str:
    """Strip control characters (header injection) and cap length."""
    return re.sub(r"[\r\n\x00-\x1f]", "", value or "")[:max_len]


def _notify_admin(subject: str, body: str) -> None:
    recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")
    if not recipient:
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Revocation admin notification failed: %s", subject)


def _admin_body(revocation: RevocationRequest) -> str:
    lines = [
        "Über den e-Recht24-Widerrufsbutton ist ein Widerruf eingegangen.",
        "",
        f"Widerrufs-ID: {revocation.revo_id}",
        f"Name: {revocation.customer_name or '(keine Angabe)'}",
        f"E-Mail: {revocation.customer_email or '(keine Angabe)'}",
        f"Bestellnummer: {revocation.order_number or '(keine Angabe)'}",
        f"Kundennummer: {revocation.customer_number or '(keine Angabe)'}",
        f"Betroffene Leistung: {revocation.relevant_service or '(keine Angabe)'}",
        f"Eingereicht am: {revocation.submitted_at or '(unbekannt)'}",
        f"Status: {revocation.get_status_display()}",
    ]
    if revocation.matched_user:
        lines.append(f"Zugeordneter Account: {revocation.matched_user.username}")
    return "\n".join(lines)


def _cancel_stripe_subscription(subscription_id: str) -> bool:
    """Cancel the subscription immediately at Stripe (statutory revocation).

    Returns True if the subscription is cancelled or already gone at Stripe.
    No refund is triggered here — refunds are handled manually in the Stripe
    dashboard.
    """
    if not getattr(settings, "STRIPE_SECRET_KEY", ""):
        logger.warning("Stripe not configured — skipping remote cancel for %s", subscription_id)
        return True
    try:
        stripe.Subscription.cancel(subscription_id)
        return True
    except stripe.error.InvalidRequestError as e:
        # Already cancelled / unknown at Stripe: nothing left to cancel remotely.
        logger.warning(
            "Stripe cancel for %s: subscription not cancellable (%s) — treating as done",
            subscription_id,
            getattr(e, "code", None),
        )
        return True
    except stripe.error.StripeError as e:
        logger.exception("Stripe cancel failed for %s status=%s", subscription_id, e.http_status)
        return False


@method_decorator(ratelimit(key="ip", rate="20/m", block=True), name="dispatch")
class Erecht24RevocationConfirmView(View):
    """Tokenized confirmation page for a pending revocation.

    GET only renders the page (link-preview bots must not trigger the
    cancellation); the actual cancel runs on CSRF-protected POST. The token
    itself is the authorization — no login required, like Django's password
    reset links.
    """

    http_method_names = ["get", "post"]
    template_name = "core/revocation_confirm.html"

    def _validate(self, revocation):
        """Return "ok", "invalid" or "expired" for a fetched revocation.

        Marks the request expired (and burns the token) when older than the
        14-day confirmation window.
        """
        if (
            revocation is None
            or revocation.status != "pending_confirmation"
            or not revocation.confirmation_token_created_at
        ):
            return "invalid"
        if timezone.now() - revocation.confirmation_token_created_at > CONFIRMATION_TOKEN_MAX_AGE:
            revocation.status = "expired"
            revocation.confirmation_token = None
            revocation.save(update_fields=["status", "confirmation_token"])
            return "expired"
        return "ok"

    def get(self, request, token):
        revocation = RevocationRequest.objects.filter(confirmation_token=token).first()
        state = self._validate(revocation)
        if state != "ok":
            return render(request, self.template_name, {"state": state}, status=410)
        return render(
            request,
            self.template_name,
            {"state": "confirm", "revocation": revocation, "token": token},
        )

    def post(self, request, token):
        # Claim the request atomically so a double-submit cannot cancel twice.
        with transaction.atomic():
            revocation = (
                RevocationRequest.objects.select_for_update()
                .filter(confirmation_token=token)
                .first()
            )
            state = self._validate(revocation)
            if state == "ok":
                revocation.status = "confirmed_cancelled"
                revocation.confirmation_token = None
                revocation.save(update_fields=["status", "confirmation_token"])
        if state != "ok":
            return render(request, self.template_name, {"state": state}, status=410)

        user = revocation.matched_user
        profile = UserProfile.objects.filter(user=user).first() if user else None
        subscription_id = profile.stripe_subscription_id if profile else None

        stripe_ok = True
        if subscription_id:
            # Stripe API call outside any DB transaction (see views_stripe H11).
            stripe_ok = _cancel_stripe_subscription(subscription_id)

        if profile:
            # Same local downgrade path as the customer.subscription.deleted
            # webhook handler; the later Stripe event then becomes a no-op.
            with transaction.atomic():
                locked = UserProfile.objects.select_for_update().get(pk=profile.pk)
                locked.stripe_subscription_id = None
                locked.stripe_price_id = None
                locked.save(update_fields=["stripe_subscription_id", "stripe_price_id"])
                _set_premium(locked, False)

        safe_name = _sanitize_for_subject(revocation.customer_name) or "(unbekannt)"
        body = _admin_body(revocation)
        if not stripe_ok:
            body += (
                "\n\nACHTUNG: Die Stripe-Kündigung ist fehlgeschlagen — bitte die "
                f"Subscription {subscription_id} manuell im Stripe-Dashboard kündigen."
            )
        _notify_admin(
            f"[Preceptly] Widerruf bestätigt und Abo gekündigt: {safe_name}",
            body,
        )
        logger.info(
            "Revocation %s confirmed; subscription %s cancelled (stripe_ok=%s)",
            revocation.revo_id,
            subscription_id,
            stripe_ok,
        )
        return render(request, self.template_name, {"state": "success"})

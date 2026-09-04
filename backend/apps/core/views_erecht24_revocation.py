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

import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from apps.core.log_safety import safe_log_value
from apps.core.models import RevocationRequest, UserProfile
from apps.core.views_stripe import _set_premium

MAX_WEBHOOK_BYTES = 64 * 1024
CONFIRMATION_TOKEN_MAX_AGE = timedelta(days=14)  # gesetzliche Widerrufsfrist

logger = logging.getLogger(__name__)

if hasattr(settings, "STRIPE_SECRET_KEY") and settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _verify_signature(raw_body: bytes, header_value: str, secret: str) -> bool:
    """Check X-Webhook-Signature ("sha256=<hex>") against HMAC-SHA256 of the raw body."""
    if not header_value or not isinstance(header_value, str):
        return False
    prefix = "sha256="
    if not header_value.startswith(prefix):
        return False
    provided = header_value[len(prefix) :].strip()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


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
        logger.exception("Revocation admin notification failed: %s", safe_log_value(subject))


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


def _match_user(customer_email: str):
    """Match the payload email against accounts (case-insensitive exact match).

    Returns (user_or_none, status): exactly one account with an active paid
    subscription -> pending_confirmation; multiple accounts -> ambiguous_match;
    otherwise (no account, or nothing to cancel) -> no_match.
    """
    if not customer_email:
        return None, "no_match"
    users = list(get_user_model().objects.filter(email__iexact=customer_email)[:2])
    if not users:
        return None, "no_match"
    if len(users) > 1:
        return None, "ambiguous_match"
    user = users[0]
    profile = UserProfile.objects.filter(user=user).first()
    has_active_subscription = profile is not None and (
        profile.subscription_tier != "free" or profile.stripe_subscription_id
    )
    if not has_active_subscription:
        return user, "no_match"
    return user, "pending_confirmation"


def _send_confirmation_email(user, token: str) -> None:
    """Send the confirmation link to the address stored on the account.

    Deliberately user.email, NOT the payload customer_email: even if both
    should normally be identical, the confirmation must reach the real
    account owner.
    """
    site_url = getattr(settings, "SITE_URL", "https://preceptly.de").rstrip("/")
    confirm_url = site_url + reverse("core:erecht24_revocation_confirm", args=[token])
    body = (
        "Guten Tag,\n\n"
        "für Ihr Preceptly-Abo ist über unser Widerrufsformular ein Widerruf "
        "eingegangen.\n\n"
        "Wenn Sie diesen Widerruf selbst eingereicht haben, bestätigen Sie ihn "
        "bitte über den folgenden Link. Erst nach Ihrer Bestätigung wird Ihr "
        "Abo gekündigt:\n\n"
        f"{confirm_url}\n\n"
        "Der Link ist 14 Tage gültig.\n\n"
        "Wenn Sie diesen Widerruf NICHT selbst eingereicht haben, ignorieren "
        "Sie diese E-Mail einfach – dann passiert nichts und Ihr Abo bleibt "
        "unverändert. Bei Fragen wenden Sie sich gerne an unseren Support.\n\n"
        "Viele Grüße\n"
        "Ihr Preceptly-Team"
    )
    try:
        send_mail(
            subject="Widerruf für Ihr Preceptly-Abo – Bestätigung erforderlich",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Revocation confirmation email to user %s failed", user.pk)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ratelimit(key="ip", rate="20/m", method="POST", block=True), name="dispatch")
class Erecht24RevocationWebhookView(View):
    """Receives revocation.submitted events from the e-recht24 revocation button.

    Never cancels anything itself — records the request and triggers the
    email confirmation flow (see module docstring).
    """

    http_method_names = ["post"]

    def post(self, request):
        secret = getattr(settings, "ERECHT24_REVOCATION_WEBHOOK_SECRET", "")
        if not secret:
            # Fail closed: without a configured secret no request can be
            # verified, so none is accepted (analogous to the SECRET_KEY
            # pattern in settings.py).
            logger.error("ERECHT24_REVOCATION_WEBHOOK_SECRET not configured — rejecting webhook")
            return JsonResponse({"code": 503, "message": "webhook not configured"}, status=503)

        content_length = request.META.get("CONTENT_LENGTH")
        if content_length is not None:
            try:
                if int(content_length) > MAX_WEBHOOK_BYTES:
                    return JsonResponse({"code": 413, "message": "payload too large"}, status=413)
            except (ValueError, TypeError):
                # Malformed Content-Length header - fall through to the real
                # body-length check below instead of trusting the header.
                logger.debug("Malformed Content-Length header: %r", content_length)
        body = request.body
        if len(body) > MAX_WEBHOOK_BYTES:
            return JsonResponse({"code": 413, "message": "payload too large"}, status=413)

        signature = request.headers.get("X-Webhook-Signature", "")
        if not _verify_signature(body, signature, secret):
            return JsonResponse({"code": 403, "message": "invalid signature"}, status=403)

        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"code": 400, "message": "invalid json"}, status=400)
        if not isinstance(parsed, dict):
            return JsonResponse({"code": 400, "message": "invalid payload"}, status=400)

        # e-recht24 documents the body as {"payload": {...}}; accept both the
        # wrapped and the unwrapped form.
        payload = parsed.get("payload") if isinstance(parsed.get("payload"), dict) else parsed

        event = payload.get("event") or request.headers.get("X-Webhook-Event", "")
        if event != "revocation.submitted":
            logger.info(
                "Ignoring e-recht24 revocation webhook event type: %s", safe_log_value(event)
            )
            return JsonResponse({"status": "ignored"}, status=200)

        data = payload.get("data")
        if not isinstance(data, dict):
            return JsonResponse({"code": 400, "message": "missing data"}, status=400)
        revo_id = str(data.get("revo_id") or "").strip()[:64]
        if not revo_id:
            return JsonResponse({"code": 400, "message": "missing revo_id"}, status=400)

        # Idempotency: webhook retries with a known revo_id are acknowledged
        # without any new action (no duplicate confirmation emails).
        if RevocationRequest.objects.filter(revo_id=revo_id).exists():
            return JsonResponse({"status": "already_processed"}, status=200)

        customer_email = str(data.get("customer_email") or "").strip()[:254]
        matched_user, status = _match_user(customer_email)

        token = None
        token_created_at = None
        if status == "pending_confirmation":
            token = secrets.token_urlsafe(32)
            token_created_at = timezone.now()

        try:
            with transaction.atomic():
                revocation = RevocationRequest.objects.create(
                    revo_id=revo_id,
                    customer_name=str(data.get("customer_name") or "")[:200],
                    customer_email=customer_email,
                    order_number=str(data.get("order_number") or "")[:100],
                    customer_number=str(data.get("customer_number") or "")[:100],
                    relevant_service=str(data.get("relevant_service") or "")[:200],
                    submitted_at=parse_datetime(str(data.get("submitted_at") or "")),
                    occurred_at=parse_datetime(str(payload.get("occurred_at") or "")),
                    status=status,
                    confirmation_token=token,
                    confirmation_token_created_at=token_created_at,
                    matched_user=matched_user,
                )
        except IntegrityError:
            # Concurrent retry created the row first — same idempotent answer.
            return JsonResponse({"status": "already_processed"}, status=200)

        if status == "pending_confirmation":
            _send_confirmation_email(matched_user, token)

        safe_name = _sanitize_for_subject(revocation.customer_name) or "(unbekannt)"
        if status == "pending_confirmation":
            subject = f"Widerruf eingegangen: {safe_name} – Bestätigung an Kunde gesendet"
        elif status == "ambiguous_match":
            subject = f"Widerruf: mehrdeutige Zuordnung – manuelle Prüfung nötig ({safe_name})"
        else:
            subject = f"Widerruf: keine Zuordnung gefunden ({safe_name})"
        _notify_admin(f"[Preceptly] {subject}", _admin_body(revocation))

        logger.info(
            "e-recht24 revocation %s recorded with status=%s",
            safe_log_value(revo_id),
            safe_log_value(status),
        )
        return JsonResponse({"status": status}, status=200)


def _cancel_stripe_subscription(subscription_id: str) -> bool:
    """Cancel the subscription immediately at Stripe (statutory revocation).

    Returns True if the subscription is cancelled or already gone at Stripe.
    No refund is triggered here — refunds are handled manually in the Stripe
    dashboard.
    """
    if not getattr(settings, "STRIPE_SECRET_KEY", ""):
        logger.warning(
            "Stripe not configured — skipping remote cancel for %s",
            safe_log_value(subscription_id),
        )
        return True
    try:
        stripe.Subscription.cancel(subscription_id)
        return True
    except stripe.error.InvalidRequestError as e:
        # Already cancelled / unknown at Stripe: nothing left to cancel remotely.
        logger.warning(
            "Stripe cancel for %s: subscription not cancellable (%s) — treating as done",
            safe_log_value(subscription_id),
            safe_log_value(getattr(e, "code", None)),
        )
        return True
    except stripe.error.StripeError as e:
        logger.exception(
            "Stripe cancel failed for %s status=%s",
            safe_log_value(subscription_id),
            safe_log_value(e.http_status),
        )
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
            safe_log_value(revocation.revo_id),
            safe_log_value(subscription_id),
            stripe_ok,
        )
        return render(request, self.template_name, {"state": "success"})

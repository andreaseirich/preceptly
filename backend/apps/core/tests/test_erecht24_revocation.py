"""Tests for the e-recht24 revocation button webhook and confirmation flow.

The webhook uses HMAC-SHA256 body signatures (unlike the legal-text push
webhook, which uses secret-in-payload). Incoming revocations must never
cancel anything directly — only the tokenized email confirmation may.
"""

import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import RevocationRequest, UserProfile

User = get_user_model()

TEST_SECRET = "test-revocation-webhook-secret"
ADMIN_EMAIL = "admin@example.com"
STRIPE_CANCEL = "apps.core.views_erecht24_revocation.stripe.Subscription.cancel"


def _sign(body: bytes, secret: str = TEST_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _payload(revo_id: str = "1234-ABC", email: str = "max@example.de") -> dict:
    return {
        "payload": {
            "event": "revocation.submitted",
            "occurred_at": "2026-01-15T10:30:00Z",
            "shop_id": "shop-uuid-1",
            "data": {
                "id": "revocation-uuid-1",
                "revo_id": revo_id,
                "customer_name": "Max Mustermann",
                "customer_email": email,
                "order_number": "ORD-123",
                "customer_number": "KD-456",
                "relevant_service": "Jahresabo Premium",
                "submitted_language": "de",
                "submitted_at": "2026-01-15T10:30:00Z",
            },
        }
    }


COMMON_SETTINGS = {
    "ERECHT24_REVOCATION_WEBHOOK_SECRET": TEST_SECRET,
    "RATELIMIT_ENABLE": False,
    "ADMIN_NOTIFICATION_EMAIL": ADMIN_EMAIL,
    "SITE_URL": "https://preceptly.de",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
}


@override_settings(**COMMON_SETTINGS)
class RevocationWebhookTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("core:erecht24_revocation_webhook")

    def _post(self, payload: dict, signature: str | None = "auto"):
        body = json.dumps(payload).encode()
        headers = {}
        if signature == "auto":
            headers["HTTP_X_WEBHOOK_SIGNATURE"] = _sign(body)
        elif signature is not None:
            headers["HTTP_X_WEBHOOK_SIGNATURE"] = signature
        return self.client.post(self.url, body, content_type="application/json", **headers)

    def _create_premium_user(self, email: str = "max@example.de"):
        user = User.objects.create_user(username="tutor", email=email, password="test")
        UserProfile.objects.create(
            user=user,
            subscription_tier="pro",
            stripe_subscription_id="sub_123",
        )
        return user

    @patch(STRIPE_CANCEL)
    def test_valid_signature_unique_match_creates_pending_and_sends_mail(self, mock_cancel):
        # Payload email deliberately differs in case: mail must go to user.email.
        user = self._create_premium_user(email="Max@Example.de")
        response = self._post(_payload(email="max@example.de"))
        self.assertEqual(response.status_code, 200)

        revocation = RevocationRequest.objects.get(revo_id="1234-ABC")
        self.assertEqual(revocation.status, "pending_confirmation")
        self.assertEqual(revocation.matched_user, user)
        self.assertTrue(revocation.confirmation_token)
        self.assertIsNotNone(revocation.confirmation_token_created_at)

        # Confirmation mail to the STORED account address (create_user
        # lowercases the domain, so user.email is "Max@example.de", which
        # still differs from the payload's "max@example.de") + admin mail.
        recipients = [addr for m in mail.outbox for addr in m.to]
        self.assertIn(user.email, recipients)
        self.assertIn(ADMIN_EMAIL, recipients)
        confirmation = next(m for m in mail.outbox if user.email in m.to)
        self.assertIn(revocation.confirmation_token, confirmation.body)
        self.assertIn("https://preceptly.de/erecht24/revocation-confirm/", confirmation.body)

        # Webhook receipt must NOT touch Stripe.
        mock_cancel.assert_not_called()

    @patch(STRIPE_CANCEL)
    def test_no_match_only_admin_mail(self, mock_cancel):
        response = self._post(_payload(email="unknown@example.de"))
        self.assertEqual(response.status_code, 200)
        revocation = RevocationRequest.objects.get(revo_id="1234-ABC")
        self.assertEqual(revocation.status, "no_match")
        self.assertIsNone(revocation.confirmation_token)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [ADMIN_EMAIL])
        mock_cancel.assert_not_called()

    @patch(STRIPE_CANCEL)
    def test_match_without_active_subscription_is_no_match(self, mock_cancel):
        user = User.objects.create_user(username="tutor", email="max@example.de", password="x")
        UserProfile.objects.create(user=user, subscription_tier="free")
        response = self._post(_payload())
        self.assertEqual(response.status_code, 200)
        revocation = RevocationRequest.objects.get(revo_id="1234-ABC")
        self.assertEqual(revocation.status, "no_match")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [ADMIN_EMAIL])
        mock_cancel.assert_not_called()

    @patch(STRIPE_CANCEL)
    def test_ambiguous_match_only_admin_mail(self, mock_cancel):
        for i in range(2):
            user = User.objects.create_user(
                username=f"tutor{i}", email="max@example.de", password="x"
            )
            UserProfile.objects.create(
                user=user, subscription_tier="pro", stripe_subscription_id=f"sub_{i}"
            )
        response = self._post(_payload())
        self.assertEqual(response.status_code, 200)
        revocation = RevocationRequest.objects.get(revo_id="1234-ABC")
        self.assertEqual(revocation.status, "ambiguous_match")
        self.assertIsNone(revocation.matched_user)
        self.assertIsNone(revocation.confirmation_token)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [ADMIN_EMAIL])
        mock_cancel.assert_not_called()

    def test_invalid_signature_returns_403_and_stores_nothing(self):
        body = json.dumps(_payload()).encode()
        response = self.client.post(
            self.url,
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="sha256=" + "0" * 64,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(RevocationRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_signature_returns_403(self):
        response = self._post(_payload(), signature=None)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(RevocationRequest.objects.count(), 0)

    def test_signature_without_sha256_prefix_returns_403(self):
        body = json.dumps(_payload()).encode()
        raw = hmac.new(TEST_SECRET.encode(), body, hashlib.sha256).hexdigest()
        response = self.client.post(
            self.url, body, content_type="application/json", HTTP_X_WEBHOOK_SIGNATURE=raw
        )
        self.assertEqual(response.status_code, 403)

    def test_duplicate_revo_id_is_idempotent(self):
        self._create_premium_user()
        first = self._post(_payload())
        self.assertEqual(first.status_code, 200)
        mails_after_first = len(mail.outbox)
        second = self._post(_payload())
        self.assertEqual(second.status_code, 200)
        self.assertEqual(json.loads(second.content)["status"], "already_processed")
        self.assertEqual(RevocationRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), mails_after_first)

    def test_unwrapped_payload_is_accepted(self):
        """Body without the documented {"payload": ...} wrapper still works."""
        self._create_premium_user()
        response = self._post(_payload()["payload"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            RevocationRequest.objects.get(revo_id="1234-ABC").status, "pending_confirmation"
        )

    def test_other_event_type_is_ignored(self):
        payload = _payload()
        payload["payload"]["event"] = "revocation.something_else"
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RevocationRequest.objects.count(), 0)

    def test_missing_revo_id_returns_400(self):
        payload = _payload()
        del payload["payload"]["data"]["revo_id"]
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        body = b"not-json{{{"
        response = self.client.post(
            self.url,
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=_sign(body),
        )
        self.assertEqual(response.status_code, 400)

    def test_oversized_body_returns_413(self):
        body = b"x" * (64 * 1024 + 1)
        response = self.client.post(
            self.url,
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=_sign(body),
        )
        self.assertEqual(response.status_code, 413)

    @override_settings(ERECHT24_REVOCATION_WEBHOOK_SECRET="")
    def test_missing_secret_fails_closed_with_503(self):
        """Unconfigured secret (production context) must reject even signed requests."""
        response = self._post(_payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(RevocationRequest.objects.count(), 0)


@override_settings(**COMMON_SETTINGS)
class RevocationConfirmTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="tutor", email="max@example.de", password="test"
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            subscription_tier="pro",
            stripe_subscription_id="sub_123",
            stripe_price_id="price_123",
        )
        self.token = "a" * 43
        self.revocation = RevocationRequest.objects.create(
            revo_id="1234-ABC",
            customer_name="Max Mustermann",
            customer_email="max@example.de",
            status="pending_confirmation",
            confirmation_token=self.token,
            confirmation_token_created_at=timezone.now(),
            matched_user=self.user,
        )

    def _url(self, token=None):
        return reverse("core:erecht24_revocation_confirm", args=[token or self.token])

    @patch(STRIPE_CANCEL)
    def test_get_shows_confirmation_page_without_cancelling(self, mock_cancel):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kündigung jetzt bestätigen")
        mock_cancel.assert_not_called()
        self.revocation.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.revocation.status, "pending_confirmation")
        self.assertEqual(self.profile.subscription_tier, "pro")

    @patch(STRIPE_CANCEL)
    def test_post_valid_token_cancels_subscription(self, mock_cancel):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 200)
        mock_cancel.assert_called_once_with("sub_123")

        self.revocation.refresh_from_db()
        self.assertEqual(self.revocation.status, "confirmed_cancelled")
        self.assertIsNone(self.revocation.confirmation_token)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.subscription_tier, "free")
        self.assertIsNone(self.profile.stripe_subscription_id)
        self.assertIsNone(self.profile.stripe_price_id)

        # Admin gets notified about the completed cancellation.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [ADMIN_EMAIL])
        self.assertIn("Widerruf bestätigt", mail.outbox[0].subject)

    @patch(STRIPE_CANCEL)
    def test_post_used_token_shows_error_without_second_cancel(self, mock_cancel):
        first = self.client.post(self._url())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(mock_cancel.call_count, 1)

        second = self.client.post(self._url())
        self.assertEqual(second.status_code, 410)
        self.assertContains(second, "ungültig", status_code=410)
        self.assertEqual(mock_cancel.call_count, 1)

    @patch(STRIPE_CANCEL)
    def test_post_expired_token_marks_expired_without_cancel(self, mock_cancel):
        self.revocation.confirmation_token_created_at = timezone.now() - timedelta(days=15)
        self.revocation.save(update_fields=["confirmation_token_created_at"])

        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "abgelaufen", status_code=410)
        mock_cancel.assert_not_called()

        self.revocation.refresh_from_db()
        self.assertEqual(self.revocation.status, "expired")
        self.assertIsNone(self.revocation.confirmation_token)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.subscription_tier, "pro")

    @patch(STRIPE_CANCEL)
    def test_get_expired_token_marks_expired(self, mock_cancel):
        self.revocation.confirmation_token_created_at = timezone.now() - timedelta(days=15)
        self.revocation.save(update_fields=["confirmation_token_created_at"])

        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 410)
        self.revocation.refresh_from_db()
        self.assertEqual(self.revocation.status, "expired")
        mock_cancel.assert_not_called()

    @patch(STRIPE_CANCEL)
    def test_post_unknown_token_shows_error(self, mock_cancel):
        response = self.client.post(self._url(token="b" * 43))
        self.assertEqual(response.status_code, 410)
        mock_cancel.assert_not_called()
        self.revocation.refresh_from_db()
        self.assertEqual(self.revocation.status, "pending_confirmation")


@override_settings(**COMMON_SETTINGS)
class RevocationEndToEndTest(TestCase):
    """Full flow: webhook -> mail token -> confirm POST -> cancelled."""

    @patch(STRIPE_CANCEL)
    def test_full_flow(self, mock_cancel):
        user = User.objects.create_user(username="tutor", email="max@example.de", password="x")
        profile = UserProfile.objects.create(
            user=user, subscription_tier="pro", stripe_subscription_id="sub_e2e"
        )

        body = json.dumps(_payload(revo_id="E2E-1")).encode()
        response = self.client.post(
            reverse("core:erecht24_revocation_webhook"),
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=_sign(body),
        )
        self.assertEqual(response.status_code, 200)
        mock_cancel.assert_not_called()

        revocation = RevocationRequest.objects.get(revo_id="E2E-1")
        token = revocation.confirmation_token
        confirm_url = reverse("core:erecht24_revocation_confirm", args=[token])

        response = self.client.post(confirm_url)
        self.assertEqual(response.status_code, 200)
        mock_cancel.assert_called_once_with("sub_e2e")
        profile.refresh_from_db()
        self.assertEqual(profile.subscription_tier, "free")
        revocation.refresh_from_db()
        self.assertEqual(revocation.status, "confirmed_cancelled")

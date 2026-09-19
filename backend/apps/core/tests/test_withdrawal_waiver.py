"""
Proof of the consumer's consent to immediate performance (loss of the
right of withdrawal, § 356 Abs. 5 BGB): recorded at checkout and confirmed
by email once the subscription exists (§ 312f Abs. 3 BGB).
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import UserProfile
from apps.core.views_stripe import WITHDRAWAL_WAIVER_TEXT


@override_settings(
    STRIPE_SECRET_KEY="sk_test_fake",
    STRIPE_PRICE_ID_MONTHLY="price_pro",
    STRIPE_ENABLED=True,
    STRIPE_PREMIUM_CHECKOUT_ENABLED=True,
)
class WaiverRecordedAtCheckoutTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_w", password="test")
        UserProfile.objects.create(user=self.user, stripe_customer_id="cus_existing")
        self.client.login(username="tutor_w", password="test")

    @patch("apps.core.views_stripe.stripe.checkout.Session.create")
    def test_both_checkout_views_record_waiver_on_profile_and_at_stripe(self, mock_create):
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/x")
        for url_name in ("core:subscription_checkout", "stripe_checkout"):
            with self.subTest(view=url_name):
                UserProfile.objects.filter(user=self.user).update(
                    withdrawal_waiver_accepted_at=None
                )
                self.client.post(reverse(url_name), data={"withdrawal_consent": "on"})

                profile = UserProfile.objects.get(user=self.user)
                self.assertIsNotNone(profile.withdrawal_waiver_accepted_at)
                call_kw = mock_create.call_args[1]
                stamp = profile.withdrawal_waiver_accepted_at.isoformat()
                self.assertEqual(call_kw["metadata"]["withdrawal_waiver_accepted_at"], stamp)
                self.assertEqual(
                    call_kw["subscription_data"]["metadata"]["withdrawal_waiver_accepted_at"],
                    stamp,
                )

    @patch("apps.core.views_stripe.stripe.checkout.Session.create")
    def test_without_consent_nothing_is_recorded(self, mock_create):
        self.client.post(reverse("core:subscription_checkout"), data={})
        mock_create.assert_not_called()
        self.assertIsNone(UserProfile.objects.get(user=self.user).withdrawal_waiver_accepted_at)


@override_settings(
    STRIPE_WEBHOOK_SECRET="whsec_fake",
    STRIPE_SECRET_KEY="sk_test_fake",
    STRIPE_PRICE_ID_PRO="price_pro",
)
class SubscriptionConfirmationEmailTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tutor_c", password="test", email="tutor@example.de"
        )
        UserProfile.objects.create(user=self.user, stripe_customer_id="cus_fake")

    def _post_checkout_completed(self, subscription, metadata=None):
        event = {
            "id": "evt_confirm",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_fake",
                    "subscription": "sub_1",
                    "metadata": {"user_id": str(self.user.id), **(metadata or {})},
                }
            },
        }
        with (
            patch("apps.core.views_stripe.stripe.Webhook.construct_event", return_value=event),
            patch("apps.core.views_stripe.stripe.Subscription.retrieve", return_value=subscription),
        ):
            return self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )

    def _subscription(self, status="active"):
        return {
            "status": status,
            "customer": "cus_fake",
            "items": {
                "data": [
                    {
                        "price": {
                            "id": "price_pro",
                            "unit_amount": 999,
                            "recurring": {"interval": "month"},
                        }
                    }
                ]
            },
        }

    def test_confirmation_contains_contract_data_and_waiver(self):
        response = self._post_checkout_completed(
            self._subscription(),
            metadata={"withdrawal_waiver_accepted_at": "2026-09-19T12:30:00+00:00"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["tutor@example.de"])
        self.assertIn("Pro", msg.body)
        self.assertIn("9,99 € pro Monat", msg.body)
        self.assertIn(WITHDRAWAL_WAIVER_TEXT, msg.body)
        self.assertIn("19.09.2026 um 14:30 Uhr", msg.body)

    def test_no_confirmation_when_subscription_not_active(self):
        self._post_checkout_completed(self._subscription(status="incomplete"))
        self.assertEqual(len(mail.outbox), 0)

    def test_mail_failure_does_not_fail_the_webhook(self):
        with patch("apps.core.views_stripe.send_mail", side_effect=OSError("smtp down")):
            response = self._post_checkout_completed(self._subscription())
        self.assertEqual(response.status_code, 200)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.stripe_subscription_id, "sub_1")

"""
Tests for Stripe subscription: checkout, portal, webhook.
"""

import json
from unittest.mock import MagicMock, patch

from apps.core.models import StripeWebhookEvent, UserProfile
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    STRIPE_SECRET_KEY="sk_test_fake",
    STRIPE_WEBHOOK_SECRET="whsec_fake",
    STRIPE_PRICE_ID_MONTHLY="price_fake",
    STRIPE_ENABLED=True,
)
class SubscriptionCheckoutTest(TestCase):
    """Checkout endpoint requires login, creates session, redirects."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        UserProfile.objects.create(user=self.user, is_premium=False)

    def test_checkout_requires_login(self):
        response = self.client.post(reverse("core:subscription_checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/login/"))

    @patch("apps.core.views_stripe.stripe.Customer.create")
    @patch("apps.core.views_stripe.stripe.checkout.Session.create")
    def test_checkout_creates_session_and_redirects(self, mock_create, mock_customer):
        mock_customer.return_value = MagicMock(id="cus_fake123")
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/fake")
        self.client.login(username="tutor", password="test")
        response = self.client.post(reverse("core:subscription_checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://checkout.stripe.com/fake")
        mock_create.assert_called_once()
        call_kw = mock_create.call_args[1]
        self.assertEqual(call_kw["mode"], "subscription")
        self.assertEqual(call_kw["customer"], "cus_fake123")


@override_settings(STRIPE_ENABLED=False)
class SubscriptionCheckoutDisabledTest(TestCase):
    """When Stripe not configured, checkout returns 503."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        UserProfile.objects.create(user=self.user)

    def test_checkout_disabled_returns_503(self):
        self.client.login(username="tutor", password="test")
        response = self.client.post(reverse("core:subscription_checkout"))
        self.assertEqual(response.status_code, 503)


@override_settings(
    STRIPE_SECRET_KEY="sk_test_fake",
    STRIPE_WEBHOOK_SECRET="whsec_fake",
    STRIPE_PRICE_ID_MONTHLY="price_fake",
    STRIPE_ENABLED=True,
)
class SubscriptionPortalTest(TestCase):
    """Portal endpoint requires login and stripe_customer_id."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile = UserProfile.objects.create(
            user=self.user, is_premium=True, stripe_customer_id="cus_fake"
        )

    def test_portal_requires_login(self):
        response = self.client.post(reverse("core:subscription_portal"))
        self.assertEqual(response.status_code, 302)

    @patch("apps.core.views_stripe.stripe.billing_portal.Session.create")
    def test_portal_creates_session_and_redirects(self, mock_create):
        mock_create.return_value = MagicMock(url="https://billing.stripe.com/fake")
        self.client.login(username="tutor", password="test")
        response = self.client.post(reverse("core:subscription_portal"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://billing.stripe.com/fake")

    def test_portal_without_customer_redirects_to_settings(self):
        self.profile.stripe_customer_id = None
        self.profile.save()
        self.client.login(username="tutor", password="test")
        response = self.client.post(reverse("core:subscription_portal"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("settings", response.url)


class StripeWebhookTest(TestCase):
    """Webhook signature verification and event handling."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_premium=False,
            stripe_customer_id="cus_fake",
            stripe_subscription_id=None,
        )

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake")
    def test_webhook_invalid_signature_returns_400(self):
        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            side_effect=Exception("Invalid signature"),
        ):
            response = self.client.post(
                reverse("stripe_webhook"),
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="invalid",
            )
        self.assertEqual(response.status_code, 400)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_SECRET_KEY="sk_test_fake")
    @patch("apps.core.views_stripe._handle_stripe_event")
    def test_webhook_success_returns_200(self, mock_handle):
        event = {
            "id": "evt_test123",
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_fake", "status": "active", "customer": "cus_fake"}},
        }
        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            return_value=event,
        ):
            response = self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )
        self.assertEqual(response.status_code, 200)
        mock_handle.assert_called_once()

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_SECRET_KEY="sk_test_fake")
    def test_webhook_subscription_updated_active_flips_premium_true(self):
        event = {
            "id": "evt_upd123",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_new",
                    "status": "active",
                    "customer": "cus_fake",
                    "metadata": {"user_id": str(self.user.id)},
                    "items": {"data": [{"price": {"id": "price_fake"}}]},
                }
            },
        }
        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            return_value=event,
        ):
            response = self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_premium)
        self.assertEqual(self.profile.stripe_subscription_id, "sub_new")

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_SECRET_KEY="sk_test_fake")
    def test_webhook_subscription_deleted_flips_premium_false(self):
        self.profile.is_premium = True
        self.profile.stripe_subscription_id = "sub_fake"
        self.profile.premium_source = "stripe"
        self.profile.save()

        event = {
            "id": "evt_del123",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_fake"}},
        }
        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            return_value=event,
        ):
            response = self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_premium)
        self.assertIsNone(self.profile.stripe_subscription_id)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_SECRET_KEY="sk_test_fake")
    def test_webhook_idempotency_same_event_twice(self):
        event = {
            "id": "evt_idem123",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_fake",
                    "status": "active",
                    "customer": "cus_fake",
                    "metadata": {"user_id": str(self.user.id)},
                    "items": {"data": [{"price": {"id": "price_fake"}}]},
                }
            },
        }

        def fake_construct(payload, sig, secret):
            return event

        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            side_effect=fake_construct,
        ):
            r1 = self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )
            r2 = self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(StripeWebhookEvent.objects.filter(event_id="evt_idem123").count(), 1)

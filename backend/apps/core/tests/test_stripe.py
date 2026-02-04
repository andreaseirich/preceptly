"""
Tests for Stripe subscription: checkout, portal, webhook, user resolution, premium rules.
"""

import json
from unittest.mock import MagicMock, patch

import stripe
from apps.core.models import StripeWebhookEvent, UserProfile
from apps.core.stripe_utils import is_premium_subscription_status, resolve_user_from_stripe_event
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse


# --- stripe_utils unit tests ---
class IsPremiumSubscriptionStatusTest(TestCase):
    """Premium True only for active/trialing."""

    def test_active_returns_true(self):
        self.assertTrue(is_premium_subscription_status("active"))

    def test_trialing_returns_true(self):
        self.assertTrue(is_premium_subscription_status("trialing"))

    def test_past_due_returns_false(self):
        self.assertFalse(is_premium_subscription_status("past_due"))

    def test_unpaid_returns_false(self):
        self.assertFalse(is_premium_subscription_status("unpaid"))

    def test_canceled_returns_false(self):
        self.assertFalse(is_premium_subscription_status("canceled"))

    def test_incomplete_returns_false(self):
        self.assertFalse(is_premium_subscription_status("incomplete"))

    def test_none_returns_false(self):
        self.assertFalse(is_premium_subscription_status(None))

    def test_empty_returns_false(self):
        self.assertFalse(is_premium_subscription_status(""))


class ResolveUserFromStripeEventTest(TestCase):
    """User resolution via metadata.user_id and customer_id fallback."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile = UserProfile.objects.create(
            user=self.user,
            stripe_customer_id="cus_abc123",
            stripe_subscription_id="sub_xyz789",
        )

    def test_resolve_user_via_metadata_user_id(self):
        event = {
            "data": {"object": {"metadata": {"user_id": str(self.user.id)}}},
        }
        result = resolve_user_from_stripe_event(event)
        self.assertEqual(result, self.profile)

    def test_resolve_user_via_customer_id_fallback(self):
        event = {"data": {"object": {"customer": "cus_abc123"}}}
        result = resolve_user_from_stripe_event(event)
        self.assertEqual(result, self.profile)

    def test_resolve_user_via_subscription_id_fallback(self):
        event = {"data": {"object": {"id": "sub_xyz789"}}}
        result = resolve_user_from_stripe_event(event)
        self.assertEqual(result, self.profile)

    def test_resolve_returns_none_when_no_mapping(self):
        event = {"data": {"object": {"customer": "cus_unknown"}}}
        result = resolve_user_from_stripe_event(event)
        self.assertIsNone(result)


# --- Checkout / Portal ---
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


# --- /stripe/checkout/ and /stripe/portal/ (STRIPE_PRICE_ID_MONTHLY) ---
@override_settings(
    STRIPE_SECRET_KEY="sk_test_fake",
    STRIPE_PRICE_ID_MONTHLY="price_premium_123",
    STRIPE_PREMIUM_CHECKOUT_ENABLED=True,
)
class StripeCheckoutPremiumTest(TestCase):
    """POST /stripe/checkout/: uses STRIPE_PRICE_ID_MONTHLY, metadata.user_id, no Customer.create when customer_id exists."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor_prem", password="test")
        UserProfile.objects.create(user=self.user, is_premium=False)

    def test_stripe_checkout_requires_login(self):
        response = self.client.post(reverse("stripe_checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/login/"))

    @patch("apps.core.views_stripe.stripe.Customer.create")
    @patch("apps.core.views_stripe.stripe.checkout.Session.create")
    def test_stripe_checkout_sets_metadata_user_id(self, mock_create, mock_customer):
        mock_customer.return_value = MagicMock(id="cus_new123")
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/premium")
        self.client.login(username="tutor_prem", password="test")
        response = self.client.post(reverse("stripe_checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://checkout.stripe.com/premium")
        call_kw = mock_create.call_args[1]
        self.assertEqual(call_kw["metadata"]["user_id"], str(self.user.id))
        self.assertEqual(call_kw["line_items"][0]["price"], "price_premium_123")
        self.assertEqual(call_kw["line_items"][0]["quantity"], 1)
        self.assertEqual(call_kw["mode"], "subscription")

    @patch("apps.core.views_stripe.stripe.checkout.Session.create")
    def test_stripe_checkout_with_existing_customer_does_not_create_customer(self, mock_create):
        UserProfile.objects.filter(user=self.user).update(stripe_customer_id="cus_existing")
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/premium")
        self.client.login(username="tutor_prem", password="test")
        with patch("apps.core.views_stripe.stripe.Customer.create") as mock_customer:
            response = self.client.post(reverse("stripe_checkout"))
        self.assertEqual(response.status_code, 302)
        mock_customer.assert_not_called()
        call_kw = mock_create.call_args[1]
        self.assertEqual(call_kw["customer"], "cus_existing")


@override_settings(
    STRIPE_SECRET_KEY="sk_test_fake",
    STRIPE_PRICE_ID_MONTHLY="price_premium_123",
    STRIPE_PREMIUM_CHECKOUT_ENABLED=True,
)
class StripePortalPremiumTest(TestCase):
    """POST /stripe/portal/: 400 without customer_id, 200 + portal_url with customer_id."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor_portal", password="test")
        self.profile = UserProfile.objects.create(
            user=self.user, stripe_customer_id="cus_portal_test"
        )

    def test_stripe_portal_without_customer_id_returns_400(self):
        self.profile.stripe_customer_id = None
        self.profile.save()
        self.client.login(username="tutor_portal", password="test")
        response = self.client.post(reverse("stripe_portal"))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    @patch("apps.core.views_stripe.stripe.billing_portal.Session.create")
    def test_stripe_portal_with_customer_id_returns_200_and_portal_url(self, mock_create):
        mock_create.return_value = MagicMock(url="https://billing.stripe.com/session/fake")
        self.client.login(username="tutor_portal", password="test")
        response = self.client.post(reverse("stripe_portal"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["portal_url"], "https://billing.stripe.com/session/fake")


# --- Webhook ---
@override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_SECRET_KEY="sk_test_fake")
class StripeWebhookTest(TestCase):
    """Webhook signature verification, event handling, idempotency."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_premium=False,
            stripe_customer_id="cus_fake",
            stripe_subscription_id=None,
        )

    def test_webhook_rejects_invalid_signature_returns_400(self):
        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("bad", "sig"),
        ):
            response = self.client.post(
                reverse("stripe_webhook"),
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="invalid",
            )
        self.assertEqual(response.status_code, 400)

    def test_webhook_without_mapping_returns_200_and_does_not_change_user(self):
        event = {
            "id": "evt_nomap123",
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_unknown", "customer": "cus_unknown"}},
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

    def test_subscription_updated_active_sets_premium_true(self):
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

    def test_subscription_updated_trialing_sets_premium_true(self):
        event = {
            "id": "evt_trial123",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_trial",
                    "status": "trialing",
                    "customer": "cus_fake",
                    "metadata": {"user_id": str(self.user.id)},
                    "items": {"data": []},
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

    def test_subscription_updated_past_due_sets_premium_false(self):
        self.profile.is_premium = True
        self.profile.stripe_subscription_id = "sub_pd"
        self.profile.premium_source = "stripe"
        self.profile.save()

        event = {
            "id": "evt_pastdue123",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_pd",
                    "status": "past_due",
                    "customer": "cus_fake",
                    "metadata": {"user_id": str(self.user.id)},
                    "items": {"data": []},
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
        self.assertFalse(self.profile.is_premium)

    def test_subscription_deleted_sets_premium_false(self):
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

    def test_idempotency_same_event_id_processed_once(self):
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
            with patch(
                "apps.core.views_stripe._handle_stripe_event",
            ) as mock_handler:
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
        mock_handler.assert_called_once()

    def test_webhook_same_event_twice_is_idempotent_and_premium_stable(self):
        """Integration test: same event twice -> premium set once, idempotent, single DB record."""
        user = User.objects.create_user(username="idem_user", password="test")
        profile = UserProfile.objects.create(
            user=user,
            is_premium=False,
            stripe_customer_id="cus_idem_test",
            stripe_subscription_id=None,
        )
        event = {
            "id": "evt_test_idempotency_123",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_idem_test",
                    "status": "active",
                    "customer": "cus_idem_test",
                    "metadata": {"user_id": str(user.id)},
                    "items": {"data": [{"price": {"id": "price_fake"}}]},
                }
            },
        }

        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            return_value=event,
        ):
            r1 = self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )
        self.assertEqual(r1.status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.is_premium)
        self.assertEqual(profile.stripe_subscription_id, "sub_idem_test")
        self.assertEqual(profile.stripe_customer_id, "cus_idem_test")

        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            return_value=event,
        ):
            r2 = self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )
        self.assertEqual(r2.status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.is_premium)
        self.assertEqual(profile.stripe_subscription_id, "sub_idem_test")
        self.assertEqual(profile.stripe_customer_id, "cus_idem_test")

        self.assertEqual(
            StripeWebhookEvent.objects.filter(event_id="evt_test_idempotency_123").count(), 1
        )


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_SECRET_KEY="sk_test_fake")
class StripeWebhookConstraintsTest(TestCase):
    """Unique constraints on event_id and stripe_customer_id."""

    def test_duplicate_event_id_unique_constraint_enforced(self):
        StripeWebhookEvent.objects.create(
            event_id="evt_uniq1", event_type="test", payload_summary={}
        )
        with self.assertRaises(IntegrityError):
            StripeWebhookEvent.objects.create(
                event_id="evt_uniq1", event_type="test", payload_summary={}
            )

    def test_webhook_duplicate_race_returns_200(self):
        event = {
            "id": "evt_race123",
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_x", "customer": "cus_fake"}},
        }

        def raise_integrity(*args, **kwargs):
            raise IntegrityError("duplicate key value")

        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            return_value=event,
        ):
            with patch(
                "apps.core.views_stripe.StripeWebhookEvent.objects.get_or_create",
                side_effect=raise_integrity,
            ):
                response = self.client.post(
                    reverse("stripe_webhook"),
                    data=json.dumps(event),
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
                )
        self.assertEqual(response.status_code, 200)

    def test_unique_constraints_customer_id(self):
        u1 = User.objects.create_user(username="u1", password="test")
        u2 = User.objects.create_user(username="u2", password="test")
        UserProfile.objects.create(user=u1, stripe_customer_id="cus_same")
        with self.assertRaises(IntegrityError):
            UserProfile.objects.create(user=u2, stripe_customer_id="cus_same")

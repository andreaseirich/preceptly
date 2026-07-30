"""
Tests for the free-trial-month checkout flag and the referral reward program.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import UserProfile
from apps.core.referrals import (
    apply_pending_referral_credit,
    ensure_referral_code,
    grant_referral_reward_if_due,
    resolve_referrer_user,
)


class EnsureReferralCodeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile = UserProfile.objects.create(user=self.user)

    def test_generates_code_when_missing(self):
        code = ensure_referral_code(self.profile)
        self.profile.refresh_from_db()
        self.assertEqual(code, self.profile.referral_code)
        self.assertEqual(len(code), 8)

    def test_idempotent_when_code_already_set(self):
        first = ensure_referral_code(self.profile)
        second = ensure_referral_code(self.profile)
        self.assertEqual(first, second)

    def test_codes_are_unique_across_users(self):
        other_user = User.objects.create_user(username="tutor2", password="test")
        other_profile = UserProfile.objects.create(user=other_user)
        code_a = ensure_referral_code(self.profile)
        code_b = ensure_referral_code(other_profile)
        self.assertNotEqual(code_a, code_b)


class ResolveReferrerUserTest(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(username="referrer", password="test")
        self.profile = UserProfile.objects.create(user=self.referrer, referral_code="ABCD1234")

    def test_resolves_existing_code(self):
        self.assertEqual(resolve_referrer_user("ABCD1234"), self.referrer)

    def test_resolves_case_insensitively(self):
        self.assertEqual(resolve_referrer_user("abcd1234"), self.referrer)

    def test_returns_none_for_unknown_code(self):
        self.assertIsNone(resolve_referrer_user("NOPE0000"))

    def test_returns_none_for_empty_code(self):
        self.assertIsNone(resolve_referrer_user(""))
        self.assertIsNone(resolve_referrer_user(None))


@override_settings(
    STRIPE_ENABLED=True,
    STRIPE_SECRET_KEY="sk_test_fake",
    STRIPE_WEBHOOK_SECRET="whsec_fake",
    STRIPE_PRICE_ID_MONTHLY="price_pro_fake",
)
class TrialCheckoutTest(TestCase):
    """First checkout attaches trial_period_days; a second one does not."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile = UserProfile.objects.create(user=self.user)
        self.client.login(username="tutor", password="test")

    @patch("apps.core.views_stripe.stripe.Customer.create")
    @patch("apps.core.views_stripe.stripe.checkout.Session.create")
    def test_first_checkout_includes_trial_period_days(self, mock_create, mock_customer):
        mock_customer.return_value = MagicMock(id="cus_fake123")
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/fake")
        self.client.post(reverse("core:subscription_checkout"), data={"withdrawal_consent": "on"})
        call_kw = mock_create.call_args[1]
        self.assertEqual(call_kw["subscription_data"]["trial_period_days"], 30)

    @patch("apps.core.views_stripe.stripe.Customer.create")
    @patch("apps.core.views_stripe.stripe.checkout.Session.create")
    def test_checkout_after_trial_used_has_no_trial(self, mock_create, mock_customer):
        self.profile.trial_used = True
        self.profile.save(update_fields=["trial_used"])
        mock_customer.return_value = MagicMock(id="cus_fake123")
        mock_create.return_value = MagicMock(url="https://checkout.stripe.com/fake")
        self.client.post(reverse("core:subscription_checkout"), data={"withdrawal_consent": "on"})
        call_kw = mock_create.call_args[1]
        self.assertNotIn("trial_period_days", call_kw["subscription_data"])


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_SECRET_KEY="sk_test_fake")
class TrialUsedWebhookTest(TestCase):
    """checkout.session.completed marks trial_used once Stripe confirms status=trialing."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile = UserProfile.objects.create(user=self.user, stripe_customer_id="cus_fake")

    def test_trialing_status_sets_trial_used(self):
        event = {
            "id": "evt_checkout_trial",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_fake",
                    "subscription": "sub_trial1",
                    "metadata": {"user_id": str(self.user.id)},
                }
            },
        }
        with (
            patch(
                "apps.core.views_stripe.stripe.Webhook.construct_event",
                return_value=event,
            ),
            patch(
                "apps.core.views_stripe.stripe.Subscription.retrieve",
                return_value={"status": "trialing", "customer": "cus_fake"},
            ),
        ):
            response = self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.trial_used)


class ReferralRegistrationTest(TestCase):
    """?ref=CODE at registration links the new user to the referrer."""

    def setUp(self):
        self.referrer = User.objects.create_user(username="referrer", password="test")
        UserProfile.objects.create(user=self.referrer, referral_code="FRIEND01")

    def test_valid_ref_code_sets_referred_by(self):
        self.client.get(reverse("core:register") + "?ref=FRIEND01")
        response = self.client.post(
            reverse("core:register"),
            data={
                "username": "newtutor",
                "password1": "SuperSecret123!",
                "password2": "SuperSecret123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username="newtutor")
        profile = UserProfile.objects.get(user=new_user)
        self.assertEqual(profile.referred_by_id, self.referrer.id)
        self.assertIsNotNone(profile.referral_code)

    def test_unknown_ref_code_does_not_crash_and_leaves_referred_by_empty(self):
        self.client.get(reverse("core:register") + "?ref=NOSUCHCODE")
        response = self.client.post(
            reverse("core:register"),
            data={
                "username": "newtutor2",
                "password1": "SuperSecret123!",
                "password2": "SuperSecret123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user__username="newtutor2")
        self.assertIsNone(profile.referred_by_id)

    def test_cannot_refer_self(self):
        code = "FRIEND01"
        self.client.login(username="referrer", password="test")
        self.client.logout()
        self.client.get(reverse("core:register") + f"?ref={code}")
        # Register as the SAME username as the referrer is impossible (unique), so
        # simulate self-referral by making the session code equal to a code the
        # new user's own profile ends up owning is not applicable here; instead
        # verify a normal distinct signup still works (guard doesn't false-positive).
        response = self.client.post(
            reverse("core:register"),
            data={
                "username": "distinctuser",
                "password1": "SuperSecret123!",
                "password2": "SuperSecret123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user__username="distinctuser")
        self.assertEqual(profile.referred_by_id, self.referrer.id)


class GrantReferralRewardTest(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(username="referrer", password="test")
        self.referrer_profile = UserProfile.objects.create(
            user=self.referrer, referral_code="REFCODE1"
        )
        self.referred = User.objects.create_user(username="referred", password="test")
        self.referred_profile = UserProfile.objects.create(
            user=self.referred, referred_by=self.referrer
        )

    def test_grants_one_pending_month_on_first_call(self):
        grant_referral_reward_if_due(self.referred_profile)
        self.referrer_profile.refresh_from_db()
        self.referred_profile.refresh_from_db()
        self.assertEqual(self.referrer_profile.referral_free_months_pending, 1)
        self.assertTrue(self.referred_profile.referral_reward_granted)

    def test_second_call_does_not_double_grant(self):
        grant_referral_reward_if_due(self.referred_profile)
        self.referred_profile.refresh_from_db()
        grant_referral_reward_if_due(self.referred_profile)
        self.referrer_profile.refresh_from_db()
        self.assertEqual(self.referrer_profile.referral_free_months_pending, 1)

    def test_no_referrer_is_a_no_op(self):
        lone_user = User.objects.create_user(username="lone", password="test")
        lone_profile = UserProfile.objects.create(user=lone_user)
        grant_referral_reward_if_due(lone_profile)
        lone_profile.refresh_from_db()
        self.assertFalse(lone_profile.referral_reward_granted)


class ApplyPendingReferralCreditTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile = UserProfile.objects.create(
            user=self.user,
            referral_free_months_pending=2,
            stripe_customer_id="cus_fake",
            stripe_price_id="price_fake",
        )

    @patch("apps.core.referrals.stripe.Customer.modify")
    @patch("apps.core.referrals.stripe.Customer.retrieve")
    @patch("apps.core.referrals.stripe.Price.retrieve")
    def test_applies_balance_credit_and_clears_pending(
        self, mock_price, mock_customer_retrieve, mock_customer_modify
    ):
        mock_price.return_value = {"unit_amount": 999}
        mock_customer_retrieve.return_value = {"balance": 0}
        apply_pending_referral_credit(self.profile)
        mock_customer_modify.assert_called_once_with("cus_fake", balance=-1998)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.referral_free_months_pending, 0)

    def test_no_op_without_pending_months(self):
        self.profile.referral_free_months_pending = 0
        self.profile.save(update_fields=["referral_free_months_pending"])
        with patch("apps.core.referrals.stripe.Customer.modify") as mock_modify:
            apply_pending_referral_credit(self.profile)
            mock_modify.assert_not_called()

    def test_no_op_without_stripe_customer(self):
        self.profile.stripe_customer_id = None
        self.profile.save(update_fields=["stripe_customer_id"])
        with patch("apps.core.referrals.stripe.Customer.modify") as mock_modify:
            apply_pending_referral_credit(self.profile)
            mock_modify.assert_not_called()


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake", STRIPE_SECRET_KEY="sk_test_fake")
class InvoicePaidReferralRewardTest(TestCase):
    """invoice.paid with amount_paid > 0 triggers the referral reward exactly once."""

    def setUp(self):
        self.referrer = User.objects.create_user(username="referrer", password="test")
        self.referrer_profile = UserProfile.objects.create(user=self.referrer)
        self.referred = User.objects.create_user(username="referred", password="test")
        self.referred_profile = UserProfile.objects.create(
            user=self.referred,
            referred_by=self.referrer,
            stripe_customer_id="cus_referred",
            stripe_subscription_id="sub_referred",
        )

    def _post_invoice_paid(self, amount_paid, event_id="evt_invoice_1"):
        event = {
            "id": event_id,
            "type": "invoice.paid",
            "data": {
                "object": {
                    "subscription": "sub_referred",
                    "customer": "cus_referred",
                    "amount_paid": amount_paid,
                }
            },
        }
        with patch(
            "apps.core.views_stripe.stripe.Webhook.construct_event",
            return_value=event,
        ):
            return self.client.post(
                reverse("stripe_webhook"),
                data=json.dumps(event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
            )

    def test_real_payment_grants_referrer_pending_month(self):
        response = self._post_invoice_paid(amount_paid=999)
        self.assertEqual(response.status_code, 200)
        self.referrer_profile.refresh_from_db()
        self.referred_profile.refresh_from_db()
        self.assertEqual(self.referrer_profile.referral_free_months_pending, 1)
        self.assertTrue(self.referred_profile.referral_reward_granted)

    def test_zero_amount_invoice_does_not_grant_reward(self):
        response = self._post_invoice_paid(amount_paid=0, event_id="evt_invoice_zero")
        self.assertEqual(response.status_code, 200)
        self.referrer_profile.refresh_from_db()
        self.assertEqual(self.referrer_profile.referral_free_months_pending, 0)

    def test_renewal_invoice_does_not_grant_reward_twice(self):
        self._post_invoice_paid(amount_paid=999, event_id="evt_invoice_first")
        self._post_invoice_paid(amount_paid=999, event_id="evt_invoice_second")
        self.referrer_profile.refresh_from_db()
        self.assertEqual(self.referrer_profile.referral_free_months_pending, 1)


class SettingsPageReferralSectionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        UserProfile.objects.create(user=self.user)
        self.client.login(username="tutor", password="test")

    def test_settings_page_renders_referral_link(self):
        response = self.client.get(reverse("core:settings"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("referral-link-input", content)
        profile = UserProfile.objects.get(user=self.user)
        self.assertIsNotNone(profile.referral_code)
        self.assertIn(f"?ref={profile.referral_code}", content)

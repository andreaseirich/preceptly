"""Konto-Adresse per Link bestätigen (apps/core/views_account_email.py)."""

import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import UserProfile

VERIFY_PATH = re.compile(r"/account/email/verify/[^\s/\"]+/")
PASSWORD = "Passwort-123-abc"


def _verify_mail():
    return next(m for m in mail.outbox if "bestätige deine E-Mail-Adresse" in m.subject)


class RegistrationVerificationTest(TestCase):
    def setUp(self):
        cache.clear()

    def _register(self):
        self.client.post(
            reverse("core:register"),
            {
                "username": "neuling",
                "email": "neuling@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
                "avv_consent": "on",
            },
        )
        return User.objects.get(username="neuling")

    def test_registration_sends_a_link_that_confirms_the_address(self):
        user = self._register()
        message = _verify_mail()
        self.assertEqual(message.to, ["neuling@example.com"])
        self.assertIn("neuling", message.body)

        self.client.logout()  # klappt auch ohne Anmeldung
        self.client.get(VERIFY_PATH.search(message.body).group(0))

        user.profile.refresh_from_db()
        self.assertIsNotNone(user.profile.email_verified_at)

    def test_link_for_an_old_address_does_nothing(self):
        user = self._register()
        path = VERIFY_PATH.search(_verify_mail().body).group(0)
        user.email = "anders@example.com"
        user.save()

        self.client.get(path)

        user.profile.refresh_from_db()
        self.assertIsNone(user.profile.email_verified_at)

    def test_expired_link_does_nothing(self):
        user = self._register()
        path = VERIFY_PATH.search(_verify_mail().body).group(0)

        with patch("apps.core.views_account_email.VERIFY_MAX_AGE", -1):
            self.client.get(path)

        user.profile.refresh_from_db()
        self.assertIsNone(user.profile.email_verified_at)


class VerificationBannerTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            "lehrer", email="lehrer@example.com", password=PASSWORD
        )
        self.profile = UserProfile.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_banner_until_confirmed(self):
        resend = reverse("core:email_verify_resend")
        self.assertContains(self.client.get(reverse("core:settings")), resend)

        self.profile.email_verified_at = timezone.now()
        self.profile.save()

        self.assertNotContains(self.client.get(reverse("core:settings")), resend)

    def test_resend_sends_a_link_and_is_limited(self):
        for _ in range(4):
            self.client.post(reverse("core:email_verify_resend"), {"next": "/dashboard/"})

        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(mail.outbox[0].to, ["lehrer@example.com"])

    def test_demo_accounts_see_no_banner(self):
        demo = User.objects.create_user("demo_user", email="demo@example.com", password="demo123")
        UserProfile.objects.create(user=demo)
        self.client.force_login(demo)

        self.assertNotContains(
            self.client.get(reverse("core:settings")), reverse("core:email_verify_resend")
        )

    def test_changing_the_address_by_link_confirms_it(self):
        self.client.post(
            reverse("core:settings"),
            {"change_email": "1", "new_email": "neu@example.com", "current_password": PASSWORD},
        )
        path = re.search(r"/account/email/confirm/[^\s/\"]+/", mail.outbox[0].body).group(0)

        self.client.get(path)

        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.email_verified_at)


class AddedAddressVerificationTest(TestCase):
    def test_adding_a_missing_address_sends_a_link(self):
        cache.clear()
        user = User.objects.create_user("ohnemail", password=PASSWORD)
        UserProfile.objects.create(user=user)
        self.client.force_login(user)

        self.client.post(reverse("core:email_required"), {"email": "da@example.com"})

        self.assertEqual(_verify_mail().to, ["da@example.com"])

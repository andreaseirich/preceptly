"""Konto-E-Mail: Nachfrage, wenn sie fehlt, und Ändern mit Bestätigungslink
(apps/core/views_account_email.py)."""

import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import UserProfile

CONFIRM_PATH = re.compile(r"/account/email/confirm/[^\s/\"]+/")
PASSWORD = "Passwort-123-abc"


class EmailRequiredTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ohnemail", password=PASSWORD)
        UserProfile.objects.create(user=self.user)

    def test_login_without_email_asks_for_it_first(self):
        response = self.client.post(
            reverse("core:login"), {"username": "ohnemail", "password": PASSWORD}
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("core:email_required")))

    def test_saving_the_address_continues_where_the_user_wanted_to_go(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("core:email_required"), {"email": "neu@example.com", "next": "/contracts/"}
        )

        self.assertRedirects(response, "/contracts/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "neu@example.com")

    def test_foreign_next_is_ignored(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("core:email_required"),
            {"email": "neu@example.com", "next": "https://boese.example.com/"},
        )

        self.assertRedirects(response, reverse("core:dashboard"), fetch_redirect_response=False)

    def test_empty_address_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("core:email_required"), {"email": ""})

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "")

    def test_banner_on_every_page_until_the_address_exists(self):
        self.client.force_login(self.user)
        self.assertContains(
            self.client.get(reverse("core:settings")),
            f'href="{reverse("core:email_required")}?next=',
        )

        self.user.email = "da@example.com"
        self.user.save()

        self.assertNotContains(
            self.client.get(reverse("core:settings")),
            f'href="{reverse("core:email_required")}?next=',
        )

    def test_demo_accounts_are_not_asked(self):
        User.objects.create_user("demo_user", password="demo123")

        response = self.client.post(
            reverse("core:login"), {"username": "demo_user", "password": "demo123"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(response["Location"].startswith(reverse("core:email_required")))


class EmailChangeTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("lehrer", email="alt@example.com", password=PASSWORD)
        UserProfile.objects.create(user=self.user, stripe_customer_id="cus_test")
        self.client.force_login(self.user)

    def _request_change(self, new="neu@example.com", password=PASSWORD):
        return self.client.post(
            reverse("core:settings"),
            {"change_email": "1", "new_email": new, "current_password": password},
        )

    def _confirm_path(self):
        return CONFIRM_PATH.search(mail.outbox[0].body).group(0)

    @patch("apps.core.views_stripe.stripe.Customer.modify")
    def test_change_needs_the_link_and_tells_the_old_address(self, mock_modify):
        self._request_change()

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alt@example.com")  # erst nach dem Klick
        self.assertEqual(mail.outbox[0].to, ["neu@example.com"])

        self.client.get(self._confirm_path())

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "neu@example.com")
        self.assertEqual(mail.outbox[1].to, ["alt@example.com"])
        self.assertIn("n***@example.com", mail.outbox[1].body)
        mock_modify.assert_not_called()  # Stripe bleibt, wie es ist

    def test_link_works_only_once(self):
        self._request_change()
        path = self._confirm_path()
        self.client.get(path)

        response = self.client.get(path, follow=True)

        texts = [str(m) for m in response.context["messages"]]
        self.assertIn("Dieser Bestätigungslink ist ungültig oder abgelaufen.", texts)

    def test_wrong_password_changes_nothing(self):
        response = self._request_change(password="falsch")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Das Passwort ist nicht richtig.")
        self.assertEqual(mail.outbox, [])

    def test_same_address_is_rejected(self):
        response = self._request_change(new="ALT@example.com")

        self.assertContains(response, "Das ist bereits deine E-Mail-Adresse.")
        self.assertEqual(mail.outbox, [])

    def test_link_of_another_account_does_nothing(self):
        self._request_change()
        path = self._confirm_path()
        other = User.objects.create_user("andere", email="x@example.com", password=PASSWORD)
        UserProfile.objects.create(user=other)
        self.client.force_login(other)

        self.client.get(path)

        other.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(other.email, "x@example.com")
        self.assertEqual(self.user.email, "alt@example.com")

    def test_expired_link_does_nothing(self):
        self._request_change()

        with patch("apps.core.views_account_email.CHANGE_MAX_AGE", -1):
            self.client.get(self._confirm_path())

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alt@example.com")

    def test_confirm_needs_login(self):
        self._request_change()
        path = self._confirm_path()
        self.client.logout()

        response = self.client.get(path)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response["Location"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alt@example.com")

    def test_too_many_attempts_are_blocked(self):
        for _ in range(5):
            self._request_change(password="falsch")

        self._request_change()

        self.assertEqual(mail.outbox, [])

    def test_demo_account_cannot_change(self):
        demo = User.objects.create_user("demo_user", email="demo@example.com", password="demo123")
        UserProfile.objects.create(user=demo)
        self.client.force_login(demo)

        self._request_change(password="demo123")

        demo.refresh_from_db()
        self.assertEqual(demo.email, "demo@example.com")
        self.assertEqual(mail.outbox, [])

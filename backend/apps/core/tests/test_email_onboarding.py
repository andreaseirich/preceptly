"""
Tests for adding an email to an account that has none (settings) and the
banner shown on every page until an address exists. Changing an existing
address: test_account_email.py.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class SettingsEmailFirstTimeAddTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_user_without_email_can_add_one(self):
        user = User.objects.create_user(username="noemail", password="test")
        self.assertEqual(user.email, "")
        self.client.login(username="noemail", password="test")
        response = self.client.post(
            reverse("core:settings"),
            {"save_email": "1", "email": "new@example.com"},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")

    def test_save_email_does_not_change_an_existing_address(self):
        user = User.objects.create_user(
            username="hasemail", password="test", email="old@example.com"
        )
        self.client.login(username="hasemail", password="test")
        response = self.client.post(
            reverse("core:settings"),
            {"save_email": "1", "email": "new@example.com"},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.email, "old@example.com")

    def test_invalid_email_on_first_add_shows_form_error(self):
        user = User.objects.create_user(username="bademail", password="test")
        self.client.login(username="bademail", password="test")
        response = self.client.post(
            reverse("core:settings"),
            {"save_email": "1", "email": "not-an-email"},
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, "")


class DashboardOnboardingBannerTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_banner_shown_when_no_email(self):
        User.objects.create_user(username="noemail2", password="test")
        self.client.login(username="noemail2", password="test")
        response = self.client.get(reverse("core:dashboard"))
        self.assertContains(response, reverse("core:email_required"))

    def test_banner_hidden_when_email_present(self):
        User.objects.create_user(username="hasemail2", password="test", email="tutor@example.com")
        self.client.login(username="hasemail2", password="test")
        response = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(response, reverse("core:email_required"))

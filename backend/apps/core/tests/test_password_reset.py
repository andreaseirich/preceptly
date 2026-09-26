"""„Passwort vergessen" für Tutoren (apps/core/views_password.py)."""

import re

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.portal.tests_portal import _make_portal_user

RESET_PATH = re.compile(r"/password-reset/[^\s/\"]+/[^\s/\"]+/")


class TutorPasswordResetTest(TestCase):
    def setUp(self):
        cache.clear()
        self.tutor = User.objects.create_user(
            "lehrerin", email="lehrerin@example.com", password="Altes-Passwort-123"
        )

    def _request(self, email):
        return self.client.post(reverse("core:password_reset"), {"email": email})

    def test_mail_names_the_username_and_carries_the_link(self):
        response = self._request("LehrerIn@Example.com")

        self.assertRedirects(response, reverse("core:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["lehrerin@example.com"])
        self.assertEqual(message.subject, "Neues Passwort für dein Preceptly-Konto")
        self.assertIn("Dein Benutzername: lehrerin", message.body)
        self.assertRegex(message.body, RESET_PATH)
        self.assertIn('<html lang="de">', message.alternatives[0][0])

    def test_unknown_address_gets_the_same_answer_and_no_mail(self):
        response = self._request("niemand@example.com")

        self.assertRedirects(response, reverse("core:password_reset_done"))
        self.assertEqual(mail.outbox, [])

    def test_portal_and_demo_accounts_get_no_link(self):
        _make_portal_user(self.tutor, "parent", "mama", "Portal-Passwort-1")
        User.objects.create_user("demo_user", email="demo@example.com", password="demo123")

        self._request("mama@example.com")
        self._request("demo@example.com")

        self.assertEqual(mail.outbox, [])

    def test_link_sets_a_new_password_once(self):
        self._request("lehrerin@example.com")
        path = RESET_PATH.search(mail.outbox[0].body).group(0)

        response = self.client.get(path, follow=True)
        self.assertContains(response, 'name="new_password1"')
        form_url = response.redirect_chain[-1][0]
        response = self.client.post(
            form_url,
            {"new_password1": "Neues-Passwort-456", "new_password2": "Neues-Passwort-456"},
        )

        self.assertRedirects(response, reverse("core:password_reset_complete"))
        self.tutor.refresh_from_db()
        self.assertTrue(self.tutor.check_password("Neues-Passwort-456"))
        response = self.client.get(path, follow=True)
        self.assertNotContains(response, 'name="new_password1"')

    @override_settings(RUN_IN_BACKGROUND=True)
    def test_response_does_not_wait_for_the_mail(self):
        with self.captureOnCommitCallbacks() as callbacks:
            self._request("lehrerin@example.com")

        self.assertEqual(mail.outbox, [])
        self.assertEqual(len(callbacks), 1)

    def test_login_page_links_to_the_reset(self):
        response = self.client.get(reverse("core:login"))

        self.assertContains(response, f'href="{reverse("core:password_reset")}"')

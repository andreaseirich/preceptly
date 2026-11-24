"""Wer sich später wo anmeldet: Eltern und Schüler gehören ins Portal, nicht in die Tutor-Anmeldung.

Befund vom 24.11.2026: Ein Elternteil hatte sein Konto aktiviert und meldete sich danach über die Startseite an, also in der Tutor-Anmeldung (Benutzername und Passwort). Die Einladung und die Aktivierungsseite nannten die Adresse
des Portals nicht, der Hinweis „Für Schüler und Eltern“ stand auf dem Handy erst nach dem Scrollen, und die Fehlermeldung verwies nicht aufs Portal.
"""

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.portal.email_service import send_portal_invite
from apps.portal.tests_portal import (
    _make_contract,
    _make_parent_link,
    _make_portal_user,
    _make_tutor,
)

PORTAL_LOGIN = "/portal/login/"


class InviteNamesThePortalAddressTest(TestCase):
    def setUp(self):
        self.tutor = _make_tutor("tutor_einladung")
        self.contract = _make_contract(self.tutor)

    def invite(self, role):
        portal_user = _make_portal_user(self.tutor, role, f"{role}_einladung")
        link = _make_parent_link(portal_user, self.contract, active=False)
        send_portal_invite(self.contract, link, f"{role}@example.org", role=role)
        return mail.outbox[-1], link

    def test_both_parts_of_the_mail_name_the_portal_address_for_later_logins(self):
        for role in ("parent", "student"):
            with self.subTest(role=role):
                message, link = self.invite(role)
                html = message.alternatives[0][0]

                self.assertIn(f"{settings.SITE_URL}{PORTAL_LOGIN}", message.body)
                self.assertIn(f"{settings.SITE_URL}{PORTAL_LOGIN}", html)
                self.assertIn("E-Mail-Adresse", message.body)
                self.assertIn(link.invite_token, message.body, "der Aktivierungslink bleibt")

    def test_the_mail_says_that_this_is_not_the_tutor_login(self):
        message, _ = self.invite("parent")

        self.assertIn("nicht über die Anmeldung für Tutoren", message.body)


class ActivationPageNamesTheAddressTest(TestCase):
    def test_the_page_shows_where_to_log_in_later(self):
        tutor = _make_tutor("tutor_aktivierung")
        portal_user = _make_portal_user(tutor, "parent", "eltern_aktivierung")
        link = _make_parent_link(portal_user, _make_contract(tutor), active=False)

        html = self.client.get(
            reverse("portal:activate", args=[link.invite_token])
        ).content.decode()

        self.assertIn(f"testserver{PORTAL_LOGIN}", html)
        self.assertIn("E-Mail-Adresse", html)
        self.assertIn("nicht über die Anmeldung für Tutoren", html)


class TutorLoginPointsParentsToThePortalTest(TestCase):
    def setUp(self):
        cache.clear()

    def page(self, lang, post=None):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
        if post is not None:
            return self.client.post(reverse("core:login"), post).content.decode()
        return self.client.get(reverse("core:login")).content.decode()

    def test_the_portal_hint_comes_before_the_login_fields_in_both_languages(self):
        for lang, hint in (
            ("de", "Das ist die Anmeldung für Tutoren"),
            ("en", "This is the tutor login"),
        ):
            with self.subTest(lang=lang):
                html = self.page(lang)

                self.assertIn(hint, html)
                self.assertLess(html.index(f'href="{PORTAL_LOGIN}"'), html.index('name="username"'))

    def test_a_failed_login_points_to_the_portal_again(self):
        for lang, hint in (("de", "Elternteil oder Schüler?"), ("en", "Parent or student?")):
            with self.subTest(lang=lang):
                html = self.page(lang, post={"username": "niemand", "password": "falsch"})
                alert = html[html.index('role="alert"') :]
                alert = alert[: alert.index("</div>")]

                self.assertIn(hint, alert)
                self.assertIn(PORTAL_LOGIN, alert)

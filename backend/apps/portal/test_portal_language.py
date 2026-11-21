"""Das Portal gibt es nur auf Deutsch, und nichts verspricht eine englische Fassung.

Seine Vorlagen sind fest auf Deutsch geschrieben; nur Bausteine, die es mit der Tutor-App teilt (Hinweisfenster), sind übersetzbar. Wer die Tutor-App auf
Englisch gestellt hat, bekäme im Portal sonst eine Mischung. `PortalGermanMiddleware` stellt alle Adressen unter /portal/ auf Deutsch; die englische Start-
und Anmeldeseite sagen offen, dass das Portal nur deutsch ist.
"""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.portal.tests_portal import (
    _make_contract,
    _make_portal_user,
    _make_student_link,
    _make_tutor,
)

NOTE_EN = "The portal is currently available in German only."
NOTE_DE = "Das Portal gibt es derzeit nur auf Deutsch."


def with_language(client, lang):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
    return client


class PortalIsGermanTest(TestCase):
    def test_portal_pages_are_german_even_with_an_english_language_cookie(self):
        for name in ("portal:login", "portal:password_reset"):
            with self.subTest(seite=name):
                response = with_language(self.client, "en").get(reverse(name))

                self.assertContains(response, '<html lang="de"')
                self.assertEqual(response["Content-Language"], "de")

    def test_the_tutor_area_keeps_following_the_language(self):
        response = with_language(self.client, "en").get(reverse("core:login"))

        self.assertContains(response, '<html lang="en"')
        self.assertEqual(response["Content-Language"], "en")

    def test_the_portal_has_no_language_choice(self):
        for name in ("portal:login", "portal:password_reset"):
            with self.subTest(seite=name):
                self.assertNotContains(self.client.get(reverse(name)), 'name="language"')

    def test_a_logged_in_portal_page_is_not_a_mix_of_languages(self):
        tutor = _make_tutor("tutor_portal_sprache")
        parent = _make_portal_user(tutor, "parent", "eltern_sprache", "pw-eltern-1")
        first = _make_contract(tutor)
        second = Contract.objects.create(
            user=tutor,
            first_name="Zweit",
            last_name="Kind",
            hourly_rate=20,
            unit_duration_minutes=60,
            start_date=first.start_date,
        )
        _make_student_link(parent, first, active=True)
        _make_student_link(parent, second, active=True)
        client = with_language(self.client, "en")
        session = client.session
        session["portal_user_id"] = parent.pk
        session.save()

        response = client.get(reverse("portal:parent_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deine Kinder")
        self.assertNotContains(response, "Your children")
        self.assertContains(
            response, "befindet sich in aktiver Entwicklung"
        )  # das Hinweisfenster der Basis, hier deutsch
        self.assertNotContains(response, "under active development")


class PortalIsNotPromisedInEnglishTest(TestCase):
    def test_the_english_landing_page_says_the_portal_is_german_only(self):
        response = with_language(self.client, "en").get(reverse("core:landing"))

        self.assertContains(response, NOTE_EN)

    def test_the_english_login_page_says_it_too(self):
        response = with_language(self.client, "en").get(reverse("core:login"))

        self.assertContains(response, NOTE_EN)

    def test_the_german_pages_do_not_need_the_note(self):
        for name in ("core:landing", "core:login"):
            with self.subTest(seite=name):
                html = with_language(self.client, "de").get(reverse(name)).content.decode()
                self.assertNotIn(NOTE_EN, html)
                self.assertNotIn(NOTE_DE, html)

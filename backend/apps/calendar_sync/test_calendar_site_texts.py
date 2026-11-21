"""Texte rund um Kalender per Adresse und Kalender-Abo: Einstellungen, Datenschutz, AVV, FAQ und Landingpage.

Die Landingpage hat einmal Funktionen als "kostenlos" gezeigt, die erst ab dem Starter-Tarif gelten
(Serien, Blockzeiten, Dokumente). Der Test unten hält die beiden Gruppen getrennt.
"""

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.calendar_sync.models import TutorCalendarFeed


class SiteTextsTest(TestCase):
    def page(self, path, lang):
        response = self.client.get(path, HTTP_ACCEPT_LANGUAGE=lang)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()

    def test_the_privacy_policy_describes_both_calendar_features(self):
        de = self.page("/legal/privacy/", "de")
        en = self.page("/legal/privacy/", "en")

        for text in (
            "Kalenderimport über geheime Adresse (Google Kalender)",
            "Kalender-Abo-Link",
            "Google Ireland Limited",
        ):
            self.assertIn(text, de)
        for text in (
            "Calendar import via secret address (Google Calendar)",
            "Calendar subscription link",
        ):
            self.assertIn(text, en)

    def test_the_privacy_policy_says_the_address_is_secret_and_titles_are_neutral_by_default(self):
        de = self.page("/legal/privacy/", "de")

        self.assertIn("nie wieder an und schreiben sie nie in Protokolle", de)
        self.assertIn("standardmäßig heißt der Titel nur „Nachhilfe“", de)

    def test_the_processing_agreement_has_the_new_clause_in_both_languages(self):
        de = self.page("/legal/avv/", "de")
        en = self.page("/legal/avv/", "en")

        self.assertIn("6.3a Nutzt der Verantwortliche den Kalenderimport per geheimer Adresse", de)
        self.assertIn("Zugangsdaten und Kalenderadressen", de)
        self.assertIn("6.3a If the Controller uses the calendar import via secret address", en)
        self.assertIn("credentials and calendar addresses", en)

    def test_the_faq_explains_google_and_the_subscription_and_no_longer_hides_the_card(self):
        html = self.page("/faq/", "de")

        self.assertIn("Kann ich auch einen Google Kalender verbinden?", html)
        self.assertIn("Wer kann den Abo-Link sehen?", html)
        self.assertNotIn("nur auf Apple-Geräten sichtbar", html)

    def test_the_landing_page_keeps_starter_features_out_of_the_free_group(self):
        html = self.page("/", "de")

        free_start = html.index("Im Free-Tarif enthalten")
        starter_start = html.index("Ab dem Starter-Tarif enthalten")
        pro_start = html.index("Ab dem Pro-Tarif enthalten")
        free_group = html[free_start:starter_start]
        starter_group = html[starter_start:pro_start]
        pro_group = html[pro_start:]
        self.assertLess(free_start, starter_start)
        self.assertLess(starter_start, pro_start)
        for starter_only in (
            "Wiederkehrende Unterrichtsstunden",
            "Blockzeiten",
            "Dokumentenverwaltung",
        ):
            self.assertNotIn(starter_only, free_group)
            self.assertIn(starter_only, starter_group)
        self.assertIn("EÜR-Export für die Steuererklärung gibt es ab Pro", free_group)
        # Meetingräume und KI-Pläne brauchen Pro (feature_flags): Sie stehen in der Pro-Gruppe, nicht bei Starter
        for pro_only in ("Integrierte Meeting-Räume", "KI-gestützte Stundenplanung"):
            self.assertNotIn(pro_only, starter_group)
            self.assertIn(pro_only, pro_group)

    def test_the_about_page_no_longer_names_framework_versions(self):
        html = self.page("/legal/about/", "de")

        self.assertNotIn("Django 5", html)
        self.assertIn("basiert auf Django und Python", html)


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SettingsInGermanTest(TestCase):
    def test_the_calendar_cards_are_translated(self):
        user = User.objects.create_user(username="tutor", password="pass")
        TutorCalendarFeed.objects.create(user=user)
        self.client.login(username="tutor", password="pass")

        html = self.client.get(reverse("core:settings"), HTTP_ACCEPT_LANGUAGE="de").content.decode()

        for text in (
            "Kalender per Adresse (Google)",
            "Geheime Adresse im iCal-Format",
            "Kalender verbinden",
            "Kalender-Abo",
            "So abonnierst du",
            "Neuen Link erstellen",
            "In Kalender-App öffnen",
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)

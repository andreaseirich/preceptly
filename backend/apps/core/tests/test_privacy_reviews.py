"""Die Datenschutzerklärung nennt die Bewertungen von Eltern und Schülern und passt zu dem, was das System tut (docs/features/feat-portal-bewertungen.md).

Bindet Text und Verhalten aneinander wie `test_privacy_statements.py`: Verantwortlicher, Daten, Rechtsgrundlage und Widerruf müssen im Text stehen, und die Wörter des Widerrufs müssen die der Schaltfläche im Portal sein.
"""

from django.test import TestCase

from apps.portal.reviews import COMMENT_MAX, NAME_MAX


class PrivacyReviewsSectionTest(TestCase):
    def page(self, lang):
        response = self.client.get("/legal/privacy/", HTTP_ACCEPT_LANGUAGE=lang)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def section(self, lang):
        heading = {
            "de": "Bewertungen von Eltern und Schülern",
            "en": "Reviews from parents and students",
        }[lang]
        html = self.page(lang)
        self.assertIn(heading, html)
        start = html.index(heading)
        return html[start : html.index("<h2>", start + len(heading))]

    def test_the_section_exists_in_both_languages_after_the_portal_section(self):
        for lang, portal in (
            ("de", "Schüler- und Elternportal"),
            ("en", "Student and parent portal"),
        ):
            with self.subTest(lang=lang):
                html = self.page(lang)

                self.assertLess(html.index(portal), html.index(self.section(lang)[:60]))

    def test_preceptly_not_the_tutor_is_named_as_controller_for_these_reviews(self):
        self.assertIn("Preceptly (nicht der Tutor)", self.section("de"))
        self.assertIn("Preceptly (not the tutor)", self.section("en"))

    def test_it_names_the_data_the_legal_basis_and_the_approval(self):
        de, en = self.section("de"), self.section("en")

        for text in (
            "Anzeigename",
            "Sternebewertung",
            "Kommentar",
            "Zeitpunkt der Einwilligung",
            "Art. 6 Abs. 1 lit. a DSGVO",
            "nach unserer Freigabe",
        ):
            with self.subTest(de=text):
                self.assertIn(text, de)
        for text in (
            "display name",
            "star rating",
            "comment",
            "time of your consent",
            "Art. 6(1)(a) GDPR",
            "after our approval",
        ):
            with self.subTest(en=text):
                self.assertIn(text, en)

    def test_it_says_that_username_and_email_are_never_shown(self):
        self.assertIn("Benutzername und E-Mail-Adresse werden nie angezeigt", self.section("de"))
        self.assertIn("user name and e-mail address are never shown", self.section("en"))

    def test_the_withdrawal_uses_the_words_of_the_button_in_the_portal(self):
        self.assertIn("„Bewertung zurückziehen“", self.section("de"))
        self.assertIn("“Withdraw review”", self.section("en"))
        self.assertIn("sofort gelöscht", self.section("de"))
        self.assertIn("deleted immediately", self.section("en"))

    def test_the_limits_in_the_text_are_the_limits_of_the_form(self):
        self.assertIn(f"höchstens {COMMENT_MAX} Zeichen", self.section("de"))
        self.assertIn(f"up to {COMMENT_MAX} characters", self.section("en"))
        self.assertEqual(NAME_MAX, 30)

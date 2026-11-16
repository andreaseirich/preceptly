"""Was die Landingpage über die KI-Stundenplanung sagt, muss zu dem passen, was tatsächlich passiert.

Früher stand dort, Schülerdaten blieben "auf deinem Gerät". Tatsächlich läuft das Sprachmodell auf eigener Hardware in
Deutschland (Datenschutzerklärung, AVV 6.2), und Namen und Kontaktdaten werden vor dem Versand entfernt (FAQ).
"""

from django.test import TestCase


class LandingAiClaimTest(TestCase):
    def page(self, path, lang):
        response = self.client.get(path, HTTP_ACCEPT_LANGUAGE=lang)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()

    def test_the_landing_page_names_where_the_model_runs_and_what_is_removed_german(self):
        html = self.page("/", "de")

        self.assertIn("Namen und Kontaktdaten werden vorher entfernt", html)
        self.assertIn("unserer eigenen Hardware in Deutschland", html)
        self.assertIn("nicht bei einem externen KI-Anbieter", html)

    def test_the_landing_page_names_where_the_model_runs_and_what_is_removed_english(self):
        html = self.page("/", "en")

        self.assertIn("names and contact details are removed first", html)
        self.assertIn("own hardware in Germany", html)

    def test_the_old_claim_is_gone_in_both_languages(self):
        for lang in ("de", "en"):
            with self.subTest(sprache=lang):
                html = self.page("/", lang)
                self.assertNotIn("bleiben lokal", html)
                self.assertNotIn("stays on your device", html)

    def test_the_privacy_policy_says_the_same_about_the_hardware(self):
        # Wird einer der beiden Texte geändert, soll der andere nicht stillschweigend widersprechen.
        self.assertIn("eigener Hardware in Deutschland", self.page("/legal/privacy/", "de"))
        self.assertIn("own hardware in Germany", self.page("/legal/privacy/", "en"))

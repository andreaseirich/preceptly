"""Aussagen auf den öffentlichen Seiten, die stimmen müssen: Umsatzsteuer (Kleinunternehmer) und "Über uns"."""

from django.test import TestCase


class SiteStatementsTest(TestCase):
    def page(self, path, lang):
        response = self.client.get(path, HTTP_ACCEPT_LANGUAGE=lang)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()

    def test_the_landing_page_says_no_vat_is_charged(self):
        self.assertIn("Gemäß § 19 UStG wird keine Umsatzsteuer berechnet", self.page("/", "de"))
        self.assertIn("No VAT is charged pursuant to § 19 UStG", self.page("/", "en"))

    def test_the_note_sits_under_the_prices(self):
        html = self.page("/", "de")

        self.assertLess(html.index("19,99 €"), html.index("keine Umsatzsteuer berechnet"))

    def test_the_terms_say_the_prices_are_final_prices(self):
        self.assertIn("4.1a Die genannten Preise sind Endpreise", self.page("/legal/terms/", "de"))
        self.assertIn("4.1a The prices stated are final prices", self.page("/legal/terms/", "en"))

    def test_the_faq_mentions_it_with_the_plans(self):
        html = self.page("/faq/", "de")

        self.assertLess(
            html.index("Business (19,99"), html.index("Kleinunternehmerregelung, § 19 UStG")
        )

    def test_the_about_page_no_longer_claims_there_are_no_external_testers(self):
        for lang, old, new in (
            (
                "de",
                "Externe Tester gibt es bisher nicht",
                "Die ersten anderen Nachhilfelehrer haben es bereits ausprobiert",
            ),
            (
                "en",
                "There are no external testers yet",
                "The first other tutors have already tried it",
            ),
        ):
            with self.subTest(sprache=lang):
                html = self.page("/legal/about/", lang)
                self.assertNotIn(old, html)
                self.assertIn(new, html)

    def test_the_about_page_no_longer_says_the_offer_to_others_is_still_a_goal(self):
        de = self.page("/legal/about/", "de")

        self.assertNotIn("künftig auch anderen Nachhilfelehrern anzubieten", de)
        self.assertIn("steht auch anderen Nachhilfelehrern offen", de)

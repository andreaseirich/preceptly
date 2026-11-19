"""Anpassung des von eRecht24 erzeugten Textes: Abschnitt ersetzen, Nachbarn nicht anfassen, im Zweifel nichts tun."""

from unittest import mock

from django.test import TestCase

from apps.core.legal_overrides import (
    CLOUDFLARE_DNS,
    apply_privacy_overrides,
    replace_heading,
    replace_section,
)

GENERATED_DE = (
    "<h2>2. Hosting und Content Delivery Networks (CDN)</h2>"
    "<h3>Externes Hosting</h3><p>Hoster-Text bleibt.</p>"
    "<h3>Cloudflare</h3><p>Cloudflare bietet ein weltweit verteiltes Content Delivery Network an.</p>"
    "<p>Dabei wird der Informationstransfer über das Netzwerk von Cloudflare geleitet.</p>"
    "<h3>Widerruf Ihrer Einwilligung</h3><p>Widerruf bleibt.</p>"
)
GENERATED_EN = (
    "<h2>2. Hosting and CDN</h2><h3>External Hosting</h3><p>Host text stays.</p>"
    "<h3>Cloudflare</h3><p>Cloudflare offers a globally distributed content delivery network.</p>"
    "<h3>Revocation of your consent</h3><p>Revocation stays.</p>"
)


class ReplaceSectionTest(TestCase):
    def test_the_section_is_replaced_up_to_the_next_heading(self):
        result = replace_section(GENERATED_DE, "h3", "Cloudflare", "<h3>Cloudflare</h3><p>NEU</p>")

        self.assertIn("<p>NEU</p>", result)
        self.assertNotIn("weltweit verteiltes Content Delivery Network", result)
        self.assertNotIn(
            "über das Netzwerk von Cloudflare geleitet", result, "auch die Absätze nach dem ersten"
        )

    def test_the_neighbouring_sections_stay_untouched(self):
        result = replace_section(GENERATED_DE, "h3", "Cloudflare", "<h3>Cloudflare</h3><p>NEU</p>")

        self.assertIn("<h3>Externes Hosting</h3><p>Hoster-Text bleibt.</p>", result)
        self.assertTrue(
            result.endswith("<h3>Widerruf Ihrer Einwilligung</h3><p>Widerruf bleibt.</p>")
        )

    def test_the_last_section_of_the_text_is_replaced_to_the_end(self):
        result = replace_section(
            "<h3>Vorher</h3><p>a</p><h3>Cloudflare</h3><p>alt</p>",
            "h3",
            "Cloudflare",
            "<h3>Cloudflare</h3>NEU",
        )

        self.assertEqual(result, "<h3>Vorher</h3><p>a</p><h3>Cloudflare</h3>NEU")

    def test_a_renamed_heading_changes_nothing_and_is_logged(self):
        html = GENERATED_DE.replace("<h3>Cloudflare</h3>", "<h3>Cloudflare-Dienst</h3>")

        with self.assertLogs("apps.core.legal_overrides", level="WARNING") as logs:
            result = replace_section(html, "h3", "Cloudflare", "<h3>Cloudflare</h3>NEU")

        self.assertEqual(result, html)
        self.assertIn("0-mal", logs.output[0])

    def test_a_heading_that_appears_twice_changes_nothing_and_is_logged(self):
        html = GENERATED_DE + "<h3>Cloudflare</h3><p>noch einmal</p>"

        with self.assertLogs("apps.core.legal_overrides", level="WARNING") as logs:
            result = replace_section(html, "h3", "Cloudflare", "<h3>Cloudflare</h3>NEU")

        self.assertEqual(result, html)
        self.assertIn("2-mal", logs.output[0])

    def test_special_characters_in_the_heading_do_not_break_the_pattern(self):
        html = "<h3>Zahlung (Stripe) + mehr?</h3><p>alt</p><h3>Ende</h3>"

        result = replace_section(
            html, "h3", "Zahlung (Stripe) + mehr?", "<h3>Zahlung (Stripe) + mehr?</h3>NEU"
        )

        self.assertEqual(result, "<h3>Zahlung (Stripe) + mehr?</h3>NEU<h3>Ende</h3>")


class ReplaceHeadingTest(TestCase):
    def test_only_the_heading_text_changes(self):
        html = "<h2>2. Hosting und CDN</h2><h3>Externes Hosting</h3><p>bleibt</p>"

        result = replace_heading(html, "h2", "2. Hosting und CDN", "2. Hosting und DNS")

        self.assertEqual(
            result, "<h2>2. Hosting und DNS</h2><h3>Externes Hosting</h3><p>bleibt</p>"
        )

    def test_a_missing_or_doubled_heading_changes_nothing_and_is_logged(self):
        for html, heading, count in (
            ("<h2>Anders</h2>", "Fehlt", "0-mal"),
            ("<h2>A</h2><h2>A</h2>", "A", "2-mal"),
        ):
            with self.subTest(count=count):
                with self.assertLogs("apps.core.legal_overrides", level="WARNING") as logs:
                    result = replace_heading(html, "h2", heading, "B")

                self.assertEqual(result, html)
                self.assertIn(count, logs.output[0])


class ApplyOverridesTest(TestCase):
    def test_cloudflare_is_described_as_dns_only_in_both_languages(self):
        for lang, generated, marker in (
            ("de", GENERATED_DE, "läuft nicht über das Netzwerk von Cloudflare"),
            ("en", GENERATED_EN, "does not run through Cloudflare"),
        ):
            with self.subTest(lang=lang):
                result = apply_privacy_overrides(generated, lang)

                self.assertIn(marker, result)
                self.assertIn(CLOUDFLARE_DNS[lang], result)
                self.assertNotIn("distributed content delivery network", result.lower())
                self.assertNotIn("verteiltes content delivery network", result.lower())
                self.assertNotIn("(CDN)", result, "die Gruppenüberschrift verspricht kein CDN mehr")

    def test_empty_text_and_unknown_languages_stay_as_they_are(self):
        self.assertEqual(apply_privacy_overrides("", "de"), "")
        self.assertIsNone(apply_privacy_overrides(None, "de"))
        self.assertEqual(apply_privacy_overrides(GENERATED_DE, "fr"), GENERATED_DE)

    def test_the_page_shows_our_version_of_the_generated_section(self):
        with mock.patch("apps.core.erecht24_service.get_privacy_policy", return_value=GENERATED_DE):
            html = self.client.get("/legal/privacy/", HTTP_ACCEPT_LANGUAGE="de").content.decode()

        self.assertIn("läuft nicht über das Netzwerk von Cloudflare", html)
        self.assertNotIn("Informationstransfer über das Netzwerk von Cloudflare geleitet", html)
        self.assertIn("Hoster-Text bleibt.", html, "übrige Abschnitte bleiben")

    def test_the_page_still_works_when_the_generated_text_changes_its_headings(self):
        changed = GENERATED_DE.replace("<h3>Cloudflare</h3>", "<h3>Cloudflare (CDN)</h3>")

        with mock.patch("apps.core.erecht24_service.get_privacy_policy", return_value=changed):
            with self.assertLogs("apps.core.legal_overrides", level="WARNING"):
                response = self.client.get("/legal/privacy/", HTTP_ACCEPT_LANGUAGE="de")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cloudflare (CDN)", response.content.decode())

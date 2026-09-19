"""
Tests for legal pages and footer integration.
"""

from django.test import Client, TestCase
from django.urls import reverse


class LegalPagesTests(TestCase):
    """Ensure legal pages render correctly."""

    def setUp(self):
        self.client = Client()

    def test_legal_pages_return_200(self):
        """Each legal page should return HTTP 200 and contain business marker."""
        pages = [
            ("core:legal_imprint", "andicode.de"),
            ("core:legal_privacy", "andicode.de"),
            ("core:legal_terms", "andicode.de"),
            ("core:legal_about", "andicode.de"),
        ]
        for name, marker in pages:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, marker)


class FooterIntegrationTests(TestCase):
    """Check that footer links appear on public pages."""

    def setUp(self):
        self.client = Client()

    def test_revocation_button_in_footer(self):
        """eRecht24 revocation button must be present in the footer on every page."""
        response = self.client.get(reverse("core:legal_imprint"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "eRecht24RevocationButton")


class LegalTextsMatchActualProcessingTests(TestCase):
    """The legal texts must describe the processing the code actually does."""

    def test_privacy_names_self_hosted_ai_not_anthropic(self):
        response = self.client.get(reverse("core:legal_privacy"))
        self.assertNotContains(response, "Anthropic")
        self.assertContains(response, "Qwen 2.5")
        self.assertContains(response, "Tailscale")

    def test_privacy_covers_calendar_sync_push_and_portal(self):
        response = self.client.get(reverse("core:legal_privacy"), HTTP_ACCEPT_LANGUAGE="de")
        for heading in (
            "Kalender-Synchronisierung (iCloud)",
            "Push-Benachrichtigungen",
            "Schüler- und Elternportal",
        ):
            self.assertContains(response, heading)

    def test_avv_lists_actual_sub_processors(self):
        response = self.client.get(reverse("core:legal_avv"), HTTP_ACCEPT_LANGUAGE="de")
        self.assertNotContains(response, "Anthropic")
        for name in (
            "Railway Corp.",
            "Cloudflare, Inc.",
            "Apple Distribution International",
            "Tailscale Inc.",
        ):
            self.assertContains(response, name)


class PortalLegalFooterTests(TestCase):
    """Imprint and privacy policy must be reachable from every portal page,
    including the ones that don't extend the portal base template."""

    def test_portal_login_links_imprint_and_privacy(self):
        for url_name in ("portal:login", "portal:password_reset"):
            with self.subTest(page=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, reverse("core:legal_imprint"))
                self.assertContains(response, reverse("core:legal_privacy"))

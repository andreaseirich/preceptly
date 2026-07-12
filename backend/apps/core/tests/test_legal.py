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

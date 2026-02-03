"""
Tests for legal placeholder pages and footer integration.
"""

from apps.core.models import UserProfile
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class LegalPagesTests(TestCase):
    """Ensure legal placeholder pages render correctly."""

    def setUp(self):
        self.client = Client()

    def test_legal_pages_return_200(self):
        """Each legal page should return HTTP 200 and contain placeholder text."""
        pages = [
            ("core:legal_imprint", "Placeholder – not legally binding yet."),
            ("core:legal_privacy", "Placeholder – not legally binding yet."),
            ("core:legal_terms", "Placeholder – not legally binding yet."),
            ("core:legal_about", "Placeholder – not legally binding yet."),
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

    def test_footer_links_render_on_public_booking(self):
        """Public booking page should render footer with legal links."""
        user = User.objects.create_user(username="tutor-footer", password="test123")
        profile = UserProfile.objects.create(user=user, public_booking_token="token-footer")

        response = self.client.get(f"/lessons/public-booking/{profile.public_booking_token}/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("/legal/imprint/", content)
        self.assertIn("/legal/privacy/", content)
        self.assertIn("/legal/terms/", content)
        self.assertIn("/legal/about/", content)

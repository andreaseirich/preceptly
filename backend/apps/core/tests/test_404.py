"""
Tests for 404 error handling.
"""

import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver", "localhost"])
class NotFoundTest(TestCase):
    """Non-existent URLs must return 404, not 500."""

    def setUp(self):
        self.client = Client()

    def test_nonexistent_url_returns_404(self):
        """GET on non-existent URL returns HTTP 404."""
        response = self.client.get("/this-page-definitely-does-not-exist-xyz/")
        self.assertEqual(response.status_code, 404)

    def test_404_response_is_html_for_browser(self):
        """404 page returns HTML (not JSON) for normal browser requests."""
        response = self.client.get("/nonexistent-route-123/")
        self.assertEqual(response.status_code, 404)
        content_type = response.get("Content-Type", "")
        self.assertIn("text/html", content_type)
        self.assertIn(b"404", response.content)

    def test_404_api_returns_json_when_accept_json(self):
        """404 for API request (Accept: application/json) returns JSON."""
        response = self.client.get(
            "/api/nonexistent/",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_404_lessons_path_returns_json_when_accept_json(self):
        """404 under /lessons/ with Accept: application/json returns JSON."""
        response = self.client.get(
            "/lessons/nonexistent-slug-xyz/",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("application/json", response["Content-Type"])
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_existing_page_still_works(self):
        """Regression: existing pages remain reachable."""
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)

    def test_404_under_lessons_path(self):
        """404 for non-existent path under /lessons/."""
        response = self.client.get("/lessons/nonexistent-page-xyz/")
        self.assertEqual(response.status_code, 404)

    def test_404_under_students_path(self):
        """404 for non-existent path under /students/."""
        response = self.client.get("/students/99999/does-not-exist/")
        self.assertEqual(response.status_code, 404)

    def test_404_public_booking_invalid_token(self):
        """404 for public booking with invalid token."""
        response = self.client.get("/lessons/public-booking/invalid-token-xyz/")
        self.assertEqual(response.status_code, 404)

    def test_404_public_booking_week_invalid_token(self):
        """404 for week API with invalid token."""
        response = self.client.get(
            "/lessons/public-booking/invalid-token/week/?year=2026&month=1&day=1"
        )
        self.assertEqual(response.status_code, 404)

    def test_404_trailing_slash_variation(self):
        """404 for clearly non-existent path (trailing slash)."""
        response = self.client.get("/lessons/nonexistent-slug-12345/")
        self.assertEqual(response.status_code, 404)

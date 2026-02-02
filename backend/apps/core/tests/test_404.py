"""
Tests for 404 error handling.
"""

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
        import json

        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_existing_page_still_works(self):
        """Regression: existing pages remain reachable."""
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)

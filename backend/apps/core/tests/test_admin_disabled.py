"""
Test that Django Admin is disabled and returns 404.

TutorFlow does not expose the Django Admin interface for security and
simplicity. The /admin/ URL must not be reachable.
"""

from django.test import Client, TestCase


class AdminDisabledTest(TestCase):
    """Verify Django Admin is not accessible."""

    def test_admin_url_returns_404(self):
        """GET /admin/ must return 404 (admin not registered)."""
        client = Client()
        response = client.get("/admin/", follow=False)
        self.assertEqual(response.status_code, 404)

    def test_admin_login_returns_404(self):
        """GET /admin/login/ must return 404."""
        client = Client()
        response = client.get("/admin/login/", follow=False)
        self.assertEqual(response.status_code, 404)

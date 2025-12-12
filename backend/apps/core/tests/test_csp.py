"""
Tests for Content Security Policy middleware.
"""

from django.test import TestCase, override_settings
from django.urls import reverse


class ContentSecurityPolicyTest(TestCase):
    """Test CSP header is set correctly."""

    def test_csp_header_present(self):
        """Test that CSP header is set when enabled."""
        response = self.client.get(reverse("core:health"))
        self.assertIn("Content-Security-Policy", response)
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertIn("style-src 'self'", csp)
        # Ensure no unsafe-inline
        self.assertNotIn("'unsafe-inline'", csp)

    @override_settings(ENABLE_CSP=False)
    def test_csp_header_disabled(self):
        """Test that CSP header is not set when disabled."""
        response = self.client.get(reverse("core:health"))
        self.assertNotIn("Content-Security-Policy", response)

    def test_csp_policy_content(self):
        """Test that CSP policy contains expected directives."""
        response = self.client.get(reverse("core:health"))
        csp = response["Content-Security-Policy"]
        # Check for key directives
        self.assertIn("img-src 'self' data:", csp)
        self.assertIn("font-src 'self'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("frame-ancestors 'self'", csp)

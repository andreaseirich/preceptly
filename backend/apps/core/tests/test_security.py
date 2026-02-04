"""
Security tests: DEBUG endpoints 404, rate limiting, headers, cookies.
"""

from django.test import TestCase, override_settings
from django.urls import reverse


class DebugEndpointsTest(TestCase):
    """test-email and test-logs return 404 when DEBUG=False."""

    @override_settings(DEBUG=False)
    def test_test_logs_returns_404_when_debug_false(self):
        response = self.client.get(reverse("core:test_logs"))
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False)
    def test_test_email_returns_404_when_debug_false(self):
        response = self.client.get(reverse("core:test_email"))
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=True)
    def test_test_logs_returns_200_when_debug_true(self):
        response = self.client.get(reverse("core:test_logs"))
        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_test_email_returns_200_when_debug_true(self):
        response = self.client.get(reverse("core:test_email"))
        self.assertEqual(response.status_code, 200)


class AuthRateLimitTest(TestCase):
    """Login and register rate limiting returns 429 after threshold."""

    def test_login_throttle_returns_429_after_failures(self):
        url = reverse("core:login")
        for _ in range(12):
            response = self.client.post(
                url,
                {"username": "nonexistent", "password": "wrong"},
                follow=False,
            )
            if response.status_code == 429:
                break
        self.assertEqual(response.status_code, 429)

    def test_register_throttle_returns_429_after_attempts(self):
        url = reverse("core:register")
        for _ in range(8):
            response = self.client.post(
                url,
                {
                    "username": f"user{_}",
                    "password1": "SecurePass123!",
                    "password2": "SecurePass123!",
                },
                follow=False,
            )
            if response.status_code == 429:
                break
        self.assertEqual(response.status_code, 429)


class SecurityHeadersTest(TestCase):
    """Responses include security headers when DEBUG=False."""

    @override_settings(DEBUG=False)
    def test_response_includes_x_content_type_options(self):
        response = self.client.get(reverse("core:landing"))
        self.assertIn("X-Content-Type-Options", response)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    @override_settings(DEBUG=False)
    def test_response_includes_referrer_policy(self):
        response = self.client.get(reverse("core:landing"))
        self.assertIn("Referrer-Policy", response)

    @override_settings(DEBUG=False)
    def test_response_includes_cross_origin_opener_policy(self):
        response = self.client.get(reverse("core:landing"))
        self.assertIn("Cross-Origin-Opener-Policy", response)
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")


class SecureCookiesTest(TestCase):
    """Cookies have Secure flag when DEBUG=False."""

    @override_settings(DEBUG=False, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_session_cookie_secure_when_production(self):
        response = self.client.get(reverse("core:login"))
        set_cookie = response.get("Set-Cookie", "")
        self.assertIn("sessionid", set_cookie)
        self.assertIn("Secure", set_cookie)

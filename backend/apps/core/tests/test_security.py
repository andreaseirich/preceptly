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
    """Responses include security headers when DEBUG=False (SecurityMiddleware)."""

    @override_settings(DEBUG=False, SECURE_CONTENT_TYPE_NOSNIFF=True)
    def test_response_includes_x_content_type_options(self):
        response = self.client.get(reverse("core:landing"))
        self.assertIn("X-Content-Type-Options", response)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    @override_settings(
        DEBUG=False,
        SECURE_REFERRER_POLICY="strict-origin-when-cross-origin",
    )
    def test_response_includes_referrer_policy_on_html(self):
        response = self.client.get(reverse("core:landing"))
        self.assertIn("Referrer-Policy", response)

    @override_settings(DEBUG=False, SECURE_CROSS_ORIGIN_OPENER_POLICY="same-origin")
    def test_response_includes_coop_on_html(self):
        response = self.client.get(reverse("core:landing"))
        self.assertIn("Cross-Origin-Opener-Policy", response)
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")

    @override_settings(
        DEBUG=False,
        SECURE_REFERRER_POLICY="strict-origin-when-cross-origin",
    )
    def test_json_404_includes_referrer_policy(self):
        response = self.client.get(
            "/nonexistent-api/",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Referrer-Policy", response)


class SecureCookiesTest(TestCase):
    """Cookies have Secure flag when DEBUG=False."""

    @override_settings(DEBUG=False, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_session_cookie_secure_when_production(self):
        response = self.client.get(reverse("core:login"))
        set_cookie = response.get("Set-Cookie", "")
        self.assertIn("sessionid", set_cookie)
        self.assertIn("Secure", set_cookie)


class LoginSessionCycleTest(TestCase):
    """Login rotates session key to reduce fixation risk."""

    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_login_cycles_session_key(self):
        """Successful login rotates session key."""
        self.client.get(reverse("core:login"))
        session_key_before = self.client.session.session_key
        self.assertIsNotNone(session_key_before)
        self.client.post(
            reverse("core:login"),
            {"username": "testuser", "password": "testpass123"},
        )
        session_key_after = self.client.session.session_key
        self.assertNotEqual(session_key_before, session_key_after)


class PublicBookingCSRFTest(TestCase):
    """Public booking POST endpoints enforce CSRF."""

    def test_verify_student_rejects_post_without_csrf(self):
        """POST to verify-student without CSRF token returns 403."""
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        resp = client.post(
            reverse("lessons:public_booking_verify_student"),
            data='{"name":"x","code":"y","tutor_token":"z"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

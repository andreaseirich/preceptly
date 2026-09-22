"""
The portal login only had the per-IP limit; a single parent or student
account could be worked through from many networks in parallel. Tutors
have had a per-account throttle all along (apps.core.auth_throttle).
"""

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

PROXY = "100.64.0.5"


@override_settings(TRUSTED_PROXIES=["100.64.0.0/10"])
class PortalLoginAccountThrottleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("portal:login")

    def _post(self, email, client_ip="203.0.113.7"):
        return self.client.post(
            self.url,
            {"email": email, "password": "wrong"},
            REMOTE_ADDR=PROXY,
            HTTP_X_FORWARDED_FOR=f"{client_ip}, 152.233.12.241",
            HTTP_ACCEPT="text/html",
        )

    def test_same_account_is_throttled_across_networks(self):
        for i in range(5):
            # every attempt from a different network, so only the per-account
            # limit can catch this
            self.assertEqual(
                self._post("parent@example.com", f"203.0.113.{i + 1}").status_code, 200
            )

        blocked = self._post("parent@example.com", "198.51.100.9")
        self.assertEqual(blocked.status_code, 429)
        self.assertTrue(blocked["Retry-After"])
        self.assertContains(blocked, "Zu viele Anmeldeversuche", status_code=429)

    def test_other_accounts_are_unaffected(self):
        for i in range(6):
            self._post("parent@example.com", f"203.0.113.{i + 1}")

        self.assertEqual(self._post("other@example.com", "198.51.100.9").status_code, 200)

    def test_empty_email_does_not_create_a_shared_counter(self):
        for i in range(6):
            self.assertEqual(self._post("", f"203.0.113.{i + 1}").status_code, 200)

"""
django-ratelimit's key="ip" used REMOTE_ADDR, which on Railway is the
internal proxy - one shared counter for every visitor, so anyone could lock
everyone out of the portal login or the public booking with ~10 requests a
minute. RATELIMIT_IP_META_KEY now points at the same client-IP logic the
tutor login throttle uses.
"""

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.core.auth_throttle import ratelimit_client_ip

PROXY = "100.64.0.5"  # inside the default TRUSTED_PROXIES range


@override_settings(TRUSTED_PROXIES=["100.64.0.0/10"])
class RatelimitClientIpTest(SimpleTestCase):
    def _request(self, remote, xff=None):
        extra = {"REMOTE_ADDR": remote}
        if xff is not None:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        return RequestFactory().get("/", **extra)

    def test_client_ip_behind_trusted_proxy(self):
        request = self._request(PROXY, "203.0.113.7, 152.233.12.241")
        self.assertEqual(ratelimit_client_ip(request), "203.0.113.7")

    def test_forwarded_header_ignored_without_trusted_proxy(self):
        request = self._request("198.51.100.4", "203.0.113.7")
        self.assertEqual(ratelimit_client_ip(request), "198.51.100.4")

    def test_garbage_forwarded_header_does_not_crash(self):
        # django-ratelimit passes the value to ipaddress.ip_network()
        self.assertEqual(ratelimit_client_ip(self._request(PROXY, "not-an-ip")), PROXY)

    def test_ipv6_client(self):
        self.assertEqual(ratelimit_client_ip(self._request(PROXY, "2001:db8::1")), "2001:db8::1")


@override_settings(TRUSTED_PROXIES=["100.64.0.0/10"])
class PortalLoginRateLimitPerClientTest(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("portal:login")

    def _post(self, client_ip, accept="text/html,application/xhtml+xml"):
        # a different account each time: this test is about the per-IP limit,
        # the per-account throttle (auth_throttle) must not interfere
        self._attempt = getattr(self, "_attempt", 0) + 1
        return self.client.post(
            self.url,
            {"email": f"nobody{self._attempt}@example.com", "password": "wrong"},
            REMOTE_ADDR=PROXY,
            HTTP_X_FORWARDED_FOR=f"{client_ip}, 152.233.12.241",
            HTTP_ACCEPT=accept,
        )

    def _post_until_blocked(self, client_ip, accept="text/html,application/xhtml+xml"):
        """django-ratelimit counts in fixed one-minute buckets, so a fixed
        number of requests can straddle a bucket boundary and never trip the
        limit. Post until it does instead."""
        for _ in range(30):
            response = self._post(client_ip, accept)
            if response.status_code == 429:
                return response
        self.fail("rate limit never kicked in")

    def test_one_visitor_hitting_the_limit_does_not_lock_out_another(self):
        self._post_until_blocked("203.0.113.7")

        # same Railway proxy, different real visitor
        self.assertEqual(self._post("198.51.100.23").status_code, 200)

    def test_blocked_browser_gets_friendly_page_with_retry_after(self):
        response = self._post_until_blocked("203.0.113.8")
        self.assertEqual(response["Retry-After"], "60")
        self.assertContains(response, "Zu viele Anfragen", status_code=429)

    def test_blocked_fetch_call_gets_json(self):
        response = self._post_until_blocked("203.0.113.9", accept="*/*")
        self.assertEqual(response.json()["success"], False)
        self.assertIn("Zu viele Anfragen", response.json()["message"])

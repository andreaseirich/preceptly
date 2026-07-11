"""
Tests for auth_throttle._get_client_ip with TRUSTED_PROXIES configured.
Verifies that the rightmost-untrusted IP from X-Forwarded-For is returned
when REMOTE_ADDR matches a trusted proxy (plain IP or CIDR range).
"""

from django.test import RequestFactory, TestCase, override_settings

from apps.core.auth_throttle import _get_client_ip, _is_trusted_proxy


class IsTrustedProxyTest(TestCase):
    def test_exact_ip_match(self):
        self.assertTrue(_is_trusted_proxy("10.0.0.1", ["10.0.0.1"]))

    def test_cidr_match(self):
        self.assertTrue(_is_trusted_proxy("10.0.0.5", ["10.0.0.0/8"]))
        self.assertTrue(_is_trusted_proxy("172.16.3.1", ["172.16.0.0/12"]))

    def test_no_match(self):
        self.assertFalse(_is_trusted_proxy("1.2.3.4", ["10.0.0.0/8", "127.0.0.1"]))

    def test_invalid_cidr_entry_skipped(self):
        # Invalid CIDR/IP entries must not raise, just be skipped.
        self.assertFalse(_is_trusted_proxy("1.2.3.4", ["not-a-cidr"]))


class GetClientIpTest(TestCase):
    factory = RequestFactory()

    def _request(self, remote_addr, xff=None):
        req = self.factory.get("/")
        req.META["REMOTE_ADDR"] = remote_addr
        if xff is not None:
            req.META["HTTP_X_FORWARDED_FOR"] = xff
        return req

    @override_settings(TRUSTED_PROXIES=["127.0.0.1"])
    def test_untrusted_remote_returns_remote_addr(self):
        req = self._request("1.2.3.4", xff="9.9.9.9")
        self.assertEqual(_get_client_ip(req), "1.2.3.4")

    @override_settings(TRUSTED_PROXIES=["10.0.0.1"])
    def test_trusted_proxy_reads_xff_rightmost_untrusted(self):
        # Client=1.2.3.4, first proxy=5.5.5.5, Railway proxy=10.0.0.1
        req = self._request("10.0.0.1", xff="1.2.3.4, 5.5.5.5")
        self.assertEqual(_get_client_ip(req), "5.5.5.5")

    @override_settings(TRUSTED_PROXIES=["10.0.0.0/8"])
    def test_cidr_trusted_proxy_reads_xff(self):
        req = self._request("10.5.6.7", xff="203.0.113.42, 10.5.6.7")
        self.assertEqual(_get_client_ip(req), "203.0.113.42")

    @override_settings(TRUSTED_PROXIES=["10.0.0.1"])
    def test_no_xff_falls_back_to_remote_addr(self):
        req = self._request("10.0.0.1")
        self.assertEqual(_get_client_ip(req), "10.0.0.1")

    @override_settings(TRUSTED_PROXIES=[])
    def test_empty_trusted_proxies_returns_remote_addr_always(self):
        req = self._request("10.0.0.1", xff="1.2.3.4")
        self.assertEqual(_get_client_ip(req), "10.0.0.1")

    @override_settings(TRUSTED_PROXIES=["10.0.0.1", "10.0.0.2"])
    def test_xff_with_multiple_trusted_hops_skipped(self):
        # Two trusted proxies in chain; client is the first non-trusted from the right.
        req = self._request("10.0.0.2", xff="client.ip, 10.0.0.1, 10.0.0.2")
        self.assertEqual(_get_client_ip(req), "client.ip")

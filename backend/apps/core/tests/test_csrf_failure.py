"""
Regression test: a CSRF failure must render our friendly German page
instead of Django's technical default, since most people hitting this are
portal users with a blocked/missing cookie (private browsing, iOS Screen
Time restrictions, an in-app browser), not an actual attack.
"""

from django.test import Client, TestCase


class CsrfFailurePageTest(TestCase):
    def test_csrf_failure_renders_friendly_german_page(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/settings/", {"save_notifications": "1"})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Cookies blockiert", status_code=403)
        self.assertContains(response, "Bildschirmzeit", status_code=403)
        self.assertNotContains(response, "CSRF verification failed", status_code=403)

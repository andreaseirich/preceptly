"""Content-Security-Policy: Kopfzeile und Meldestelle."""

import json

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.csp import ContentSecurityPolicyMiddleware, policy_value
from apps.core.models import RequestLog

REPORT_ONLY = "Content-Security-Policy-Report-Only"
ENFORCED = "Content-Security-Policy"


class PolicyHeaderTest(TestCase):
    def test_html_pages_carry_the_report_only_header(self):
        response = self.client.get(reverse("core:login"))

        self.assertIn(REPORT_ONLY, response)
        self.assertNotIn(ENFORCED, response)
        self.assertIn("report-uri /csp-report/", response[REPORT_ONLY])
        self.assertIn("default-src 'self'", response[REPORT_ONLY])

    def test_erecht24_revocation_script_is_allowed(self):
        # Ohne diese Quelle wäre der gesetzlich nötige Widerrufs-Button tot.
        policy = policy_value()

        self.assertIn(
            "script-src 'self' 'unsafe-inline' https://widerrufsbutton-cdn.e-recht24.de", policy
        )

    def test_non_html_responses_stay_untouched(self):
        response = self.client.get("/health/")

        self.assertNotIn(REPORT_ONLY, response)

    def test_enforcing_mode_uses_the_other_header(self):
        with override_settings(CSP_REPORT_ONLY=False):
            middleware = ContentSecurityPolicyMiddleware(lambda request: _html_response())
            response = middleware(None)

        self.assertIn(ENFORCED, response)
        self.assertNotIn(REPORT_ONLY, response)


def _html_response():
    from django.http import HttpResponse

    return HttpResponse("<p>Seite</p>", content_type="text/html; charset=utf-8")


class ReportEndpointTest(TestCase):
    def setUp(self):
        cache.clear()

    def _post(self, payload):
        return self.client.post(
            reverse("core:csp_report"),
            data=json.dumps(payload),
            content_type="application/csp-report",
        )

    def test_valid_report_is_accepted_and_logged_once(self):
        payload = {
            "csp-report": {
                "document-uri": "https://preceptly.de/lessons/1/",
                "effective-directive": "script-src",
                "blocked-uri": "https://boese.example.com/x.js",
            }
        }

        with self.assertLogs("apps.core.views_csp", level="WARNING") as logs:
            self.assertEqual(self._post(payload).status_code, 204)
        self.assertIn("boese.example.com", logs.output[0])

        # Gleicher Verstoß erneut: angenommen, aber nicht noch einmal protokolliert.
        with self.assertNoLogs("apps.core.views_csp", level="WARNING"):
            self.assertEqual(self._post(payload).status_code, 204)

    def test_garbage_is_rejected(self):
        response = self.client.post(
            reverse("core:csp_report"),
            data="kein json",
            content_type="application/csp-report",
        )

        self.assertEqual(response.status_code, 400)

    def test_oversized_report_is_rejected(self):
        payload = {"csp-report": {"blocked-uri": "x" * 9000}}

        self.assertEqual(self._post(payload).status_code, 400)

    def test_reports_do_not_show_up_in_the_access_statistics(self):
        RequestLog.objects.all().delete()

        self._post({"csp-report": {"blocked-uri": "https://example.com/a.js"}})

        self.assertEqual(RequestLog.objects.count(), 0)

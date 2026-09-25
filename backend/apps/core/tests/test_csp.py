"""Content-Security-Policy: Kopfzeile und Meldestelle."""

import json

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.core.csp import ContentSecurityPolicyMiddleware, policy_value
from apps.core.models import RequestLog
from apps.core.views_csp import MAX_DISTINCT_PER_HOUR

REPORT_ONLY = "Content-Security-Policy-Report-Only"
ENFORCED = "Content-Security-Policy"


class PolicyHeaderTest(TestCase):
    def test_html_pages_carry_the_report_only_header(self):
        response = self.client.get(reverse("core:login"))

        self.assertIn(REPORT_ONLY, response)
        self.assertNotIn(ENFORCED, response)
        self.assertIn("report-uri /csp-report/", response[REPORT_ONLY])
        self.assertIn("default-src 'self'", response[REPORT_ONLY])

    def test_revocation_form_can_load_and_submit(self):
        """Der gesetzlich nötige Widerruf muss sich öffnen UND absenden lassen.

        Quellen ermittelt am 24.09.2026 im Melde-Modus und aus den Skripten von
        e-Recht24. Fehlt die API in connect-src, öffnet sich das Fenster, aber
        der Widerruf wird beim Absenden blockiert - ohne sichtbaren Fehler."""
        directives = _parse(policy_value())
        needed = {
            "style-src": ["https://widerrufsbutton-cdn.e-recht24.de"],
            "script-src": [
                "https://widerrufsbutton-cdn.e-recht24.de",
                "https://cdn.jsdelivr.net",
                "'wasm-unsafe-eval'",
            ],
            "connect-src": [
                "https://widerrufsbutton.e-recht24.de",
                "https://api.friendlycaptcha.com",
            ],
            "worker-src": ["blob:"],
        }
        for directive, sources in needed.items():
            for source in sources:
                with self.subTest(richtlinie=directive, quelle=source):
                    self.assertIn(source, directives[directive])

    def test_no_eval_for_javascript(self):
        # WebAssembly ja, eval() nein - das wäre ein Freibrief für jedes Skript.
        directives = _parse(policy_value())

        self.assertNotIn("'unsafe-eval'", directives["script-src"])

    def test_non_html_responses_stay_untouched(self):
        response = self.client.get("/health/")

        self.assertNotIn(REPORT_ONLY, response)

    def test_enforcing_mode_uses_the_other_header(self):
        with override_settings(CSP_REPORT_ONLY=False):
            middleware = ContentSecurityPolicyMiddleware(lambda request: _html_response())
            response = middleware(RequestFactory().get("/"))

        self.assertIn(ENFORCED, response)
        self.assertNotIn(REPORT_ONLY, response)


def _parse(policy):
    """Richtlinie in {Richtlinie: [Quellen]} zerlegen."""
    result = {}
    for part in policy.split(";"):
        tokens = part.split()
        if tokens:
            result[tokens[0]] = tokens[1:]
    return result


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

    def test_line_breaks_cannot_forge_log_lines(self):
        payload = {
            "csp-report": {
                "document-uri": "https://preceptly.de/\nERROR gefälschte Zeile",
                "effective-directive": "script-src\r\nCRITICAL noch eine",
                "blocked-uri": "https://boese.example.com/\u2028x.js",
            }
        }

        with self.assertLogs("apps.core.views_csp", level="WARNING") as logs:
            self.assertEqual(self._post(payload).status_code, 204)
        message = logs.records[0].getMessage()
        self.assertEqual(len(message.splitlines()), 1)
        self.assertIn("gefälschte Zeile", message)  # Inhalt bleibt lesbar

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

    def test_only_the_origin_counts_for_deduplication(self):
        first = {
            "csp-report": {
                "effective-directive": "img-src",
                "blocked-uri": "https://x.example.com/a.png",
            }
        }
        second = {
            "csp-report": {
                "effective-directive": "img-src",
                "blocked-uri": "https://x.example.com/b.png",
            }
        }

        with self.assertLogs("apps.core.views_csp", level="WARNING"):
            self._post(first)
        # Gleiche Quelle, anderer Pfad: kein zweiter Logeintrag.
        with self.assertNoLogs("apps.core.views_csp", level="WARNING"):
            self._post(second)

    # Ohne Drosselung, sonst greift vor der Mengenbegrenzung das Rate-Limit.
    @override_settings(RATELIMIT_ENABLE=False)
    def test_flood_of_distinct_sources_stops_being_logged(self):
        for i in range(MAX_DISTINCT_PER_HOUR):
            self._post(
                {
                    "csp-report": {
                        "effective-directive": "img-src",
                        "blocked-uri": f"https://h{i}.example.com/a.png",
                    }
                }
            )

        with self.assertNoLogs("apps.core.views_csp", level="WARNING"):
            response = self._post(
                {
                    "csp-report": {
                        "effective-directive": "img-src",
                        "blocked-uri": "https://spaet.example.com/a.png",
                    }
                }
            )
        # Angenommen wird der Bericht weiterhin, nur eben nicht mehr protokolliert.
        self.assertEqual(response.status_code, 204)

    def test_reports_do_not_show_up_in_the_access_statistics(self):
        RequestLog.objects.all().delete()

        self._post({"csp-report": {"blocked-uri": "https://example.com/a.js"}})

        self.assertEqual(RequestLog.objects.count(), 0)

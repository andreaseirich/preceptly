import logging

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase

from apps.core.log_filters import BelowError, SkipNotFound


class SkipNotFoundFilterTest(SimpleTestCase):
    def _record(self, status_code=None):
        record = logging.LogRecord("django.request", logging.WARNING, "", 0, "x", None, None)
        if status_code is not None:
            record.status_code = status_code
        return record

    def test_drops_404(self):
        self.assertFalse(SkipNotFound().filter(self._record(404)))

    def test_keeps_other_statuses_and_plain_records(self):
        for code in (400, 403, 429, 500):
            self.assertTrue(SkipNotFound().filter(self._record(code)))
        self.assertTrue(SkipNotFound().filter(self._record()))


class RequestLoggingTest(TestCase):
    def test_django_messages_are_not_printed_twice(self):
        self.assertFalse(logging.getLogger("django").propagate)

    def test_404_is_not_logged_as_warning(self):
        with self.assertNoLogs("django.request", level="WARNING"):
            response = self.client.get("/.env")
        self.assertEqual(response.status_code, 404)

    def test_403_is_still_logged(self):
        # POST without CSRF token
        client = Client(enforce_csrf_checks=True)
        with self.assertLogs("django.security.csrf", level="WARNING"):
            response = client.post("/login/", {}, HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 403)


class ErrorStreamTest(SimpleTestCase):
    """Railway wertet stderr als Fehler - dort dürfen nur echte Fehler landen."""

    def test_below_error_filter(self):
        f = BelowError()
        self.assertTrue(f.filter(logging.makeLogRecord({"levelno": logging.WARNING})))
        self.assertFalse(f.filter(logging.makeLogRecord({"levelno": logging.ERROR})))
        self.assertFalse(f.filter(logging.makeLogRecord({"levelno": logging.CRITICAL})))

    def test_console_splits_by_level(self):
        handlers = settings.LOGGING["handlers"]

        self.assertEqual(getattr(handlers["console"]["stream"], "name", ""), "<stdout>")
        self.assertIn("below_error", handlers["console"]["filters"])
        self.assertEqual(getattr(handlers["console_errors"]["stream"], "name", ""), "<stderr>")
        self.assertEqual(handlers["console_errors"]["level"], "ERROR")

    def test_every_console_logger_also_reports_errors(self):
        loggers = {**settings.LOGGING["loggers"], "root": settings.LOGGING["root"]}
        for name, cfg in loggers.items():
            handlers = cfg.get("handlers", [])
            if "console" in handlers:
                with self.subTest(logger=name):
                    self.assertIn("console_errors", handlers)

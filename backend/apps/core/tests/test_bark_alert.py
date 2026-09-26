import logging
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.core.bark_alert import BarkErrorHandler


class BarkErrorHandlerFormatSourceTest(SimpleTestCase):
    def test_format_source_with_exception_uses_last_traceback_frame(self):
        logger = logging.getLogger("bark_alert_test")
        record = None

        class _CapturingHandler(logging.Handler):
            def emit(self, rec):
                nonlocal record
                record = rec

        logger.addHandler(_CapturingHandler())
        try:
            raise ValueError("boom")
        except ValueError:
            logger.error("something failed", exc_info=True)

        source = BarkErrorHandler._format_source(record)
        self.assertIn("ValueError", source)
        self.assertIn("test_bark_alert.py", source)

    def test_format_source_without_exception_names_only_the_location(self):
        """Der Meldungstext kann Adressen enthalten - er gehört nicht auf den Sperrbildschirm."""
        record = logging.LogRecord(
            name="apps.core.views_account_email",
            level=logging.ERROR,
            pathname="/app/backend/apps/core/views_account_email.py",
            lineno=42,
            msg="Mail an lehrerin@example.com fehlgeschlagen",
            args=(),
            exc_info=None,
        )
        source = BarkErrorHandler._format_source(record)
        self.assertEqual(
            source, "apps.core.views_account_email in apps/core/views_account_email.py:42"
        )
        self.assertNotIn("@", source)


@override_settings(
    BARK_SERVER_URL="https://bark.example.test",
    BARK_DEVICE_KEY="testkey",
    BARK_AUTH_USER="user",
    BARK_AUTH_PASSWORD="pass",
)
class BarkErrorHandlerEmitTest(SimpleTestCase):
    def setUp(self):
        cache.clear()  # die Bremse merkt sich Fundstellen im Cache

    def test_same_source_is_reported_once_per_window(self):
        handler = BarkErrorHandler()

        def record(lineno):
            return logging.LogRecord("apps.x", logging.ERROR, "x", lineno, "oops", (), None)

        with patch("apps.core.bark_alert.requests.get") as mock_get:
            handler.emit(record(1))
            handler.emit(record(1))
            handler.emit(record(2))

        self.assertEqual(mock_get.call_count, 2)

    def test_emit_calls_bark_api_with_passive_level(self):
        handler = BarkErrorHandler()
        record = logging.LogRecord(
            name="django",
            level=logging.ERROR,
            pathname="x",
            lineno=1,
            msg="oops",
            args=(),
            exc_info=None,
        )
        with patch("apps.core.bark_alert.requests.get") as mock_get:
            handler.emit(record)

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn("testkey", args[0])
        self.assertEqual(kwargs["params"]["level"], "passive")
        self.assertEqual(kwargs["auth"], ("user", "pass"))

    @override_settings(BARK_SERVER_URL="", BARK_DEVICE_KEY="")
    def test_emit_is_noop_without_configuration(self):
        handler = BarkErrorHandler()
        record = logging.LogRecord(
            name="django",
            level=logging.ERROR,
            pathname="x",
            lineno=1,
            msg="oops",
            args=(),
            exc_info=None,
        )
        with patch("apps.core.bark_alert.requests.get") as mock_get:
            handler.emit(record)
        mock_get.assert_not_called()

    def test_emit_swallows_request_errors(self):
        handler = BarkErrorHandler()
        record = logging.LogRecord(
            name="django",
            level=logging.ERROR,
            pathname="x",
            lineno=1,
            msg="oops",
            args=(),
            exc_info=None,
        )
        with patch("apps.core.bark_alert.requests.get", side_effect=Exception("network down")):
            handler.emit(record)  # darf nicht werfen

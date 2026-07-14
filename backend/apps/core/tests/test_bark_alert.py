import logging
from unittest.mock import patch

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

    def test_format_source_without_exception_uses_message(self):
        record = logging.LogRecord(
            name="x",
            level=logging.ERROR,
            pathname="x",
            lineno=1,
            msg="plain message",
            args=(),
            exc_info=None,
        )
        self.assertEqual(BarkErrorHandler._format_source(record), "plain message")


@override_settings(
    BARK_SERVER_URL="https://bark.example.test",
    BARK_DEVICE_KEY="testkey",
    BARK_AUTH_USER="user",
    BARK_AUTH_PASSWORD="pass",
)
class BarkErrorHandlerEmitTest(SimpleTestCase):
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

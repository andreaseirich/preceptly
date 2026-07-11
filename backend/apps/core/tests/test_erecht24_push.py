"""Tests for Erecht24PushView – e-recht24 secret-in-payload protocol."""

import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.core.erecht24_service import _sanitize_html


class SanitizeHtmlTest(TestCase):
    """_sanitize_html must strip script tags while keeping allowed tags."""

    def test_script_tags_stripped(self):
        result = _sanitize_html("<p>Hello</p><script>alert(1)</script>")
        self.assertNotIn("<script", result)
        self.assertIn("<p>", result)

    def test_allowed_tags_preserved(self):
        result = _sanitize_html('<p>Text <a href="https://example.com">link</a></p>')
        self.assertIn("<a", result)
        self.assertIn("https://example.com", result)

    def test_disallowed_tag_stripped(self):
        result = _sanitize_html("<p>Text</p><iframe src='x'></iframe>")
        self.assertNotIn("iframe", result)

    def test_length_limit_raises(self):
        with self.assertRaises(ValueError):
            _sanitize_html("x" * 100_001)


TEST_SECRET = "test-push-secret-value"
PUSH_URL = "core:erecht24_push"


@override_settings(ERECHT24_PUSH_SECRET=TEST_SECRET)
class Erecht24PushViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse(PUSH_URL)

    def _post_form(self, data):
        return self.client.post(self.url, data)

    def _post_json(self, data):
        return self.client.post(self.url, json.dumps(data), content_type="application/json")

    def test_ping_form_urlencoded(self):
        """Correct secret + ping type via form POST returns 200 with pong."""
        response = self._post_form({"erecht24_secret": TEST_SECRET, "erecht24_type": "ping"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data.get("message"), "pong")

    def test_ping_json(self):
        """Correct secret + ping type via JSON POST returns 200 with pong."""
        response = self._post_json({"erecht24_secret": TEST_SECRET, "erecht24_type": "ping"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data.get("message"), "pong")

    def test_wrong_secret_returns_403(self):
        """Wrong erecht24_secret must return 403."""
        response = self._post_form({"erecht24_secret": "wrong-secret", "erecht24_type": "ping"})
        self.assertEqual(response.status_code, 403)

    def test_missing_secret_returns_403(self):
        """Missing erecht24_secret must return 403."""
        response = self._post_form({"erecht24_type": "ping"})
        self.assertEqual(response.status_code, 403)

    def test_unknown_type_returns_400(self):
        """Valid secret but unknown erecht24_type must return 400."""
        response = self._post_form({"erecht24_secret": TEST_SECRET, "erecht24_type": "unknown"})
        self.assertEqual(response.status_code, 400)

    def test_imprint_calls_pull_imprint(self):
        """erecht24_type=imprint with valid secret calls pull_imprint()."""
        with patch("apps.core.erecht24_service.pull_imprint") as mock_pull:
            response = self._post_form({"erecht24_secret": TEST_SECRET, "erecht24_type": "imprint"})
        self.assertEqual(response.status_code, 200)
        mock_pull.assert_called_once()

    def test_invalid_json_body_returns_400(self):
        """Malformed JSON body must return 400."""
        response = self.client.post(self.url, b"not-valid-json{{{", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_oversized_body_returns_413(self):
        """Body exceeding MAX_WEBHOOK_BYTES must return 413."""
        big = b"x" * (64 * 1024 + 1)
        response = self.client.post(self.url, big, content_type="application/octet-stream")
        self.assertEqual(response.status_code, 413)

    @override_settings(ERECHT24_PUSH_SECRET="")
    def test_unconfigured_secret_returns_403(self):
        """Empty ERECHT24_PUSH_SECRET must cause handle_push to return 403."""
        response = self._post_form({"erecht24_secret": "", "erecht24_type": "ping"})
        self.assertEqual(response.status_code, 403)

    def test_non_string_secret_in_payload_returns_403_not_500(self):
        """A non-string erecht24_secret value (e.g. int) must not raise TypeError — returns 403."""
        response = self._post_json({"erecht24_secret": 12345, "erecht24_type": "ping"})
        self.assertEqual(response.status_code, 403)

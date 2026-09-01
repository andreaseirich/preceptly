"""
Tests für LLM-Client (mit Mock-Requests).
"""

from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase, override_settings

from apps.ai.client import LLMClient, LLMClientError


class LLMClientTest(TestCase):
    """Tests für LLM-Client."""

    def setUp(self):
        """Set up test data."""
        # Temporäre Settings für Tests
        self.original_key = settings.LLM_API_KEY
        settings.LLM_API_KEY = "test-key"

    def tearDown(self):
        """Restore original settings."""
        settings.LLM_API_KEY = self.original_key

    @patch.dict("os.environ", {"MOCK_LLM": "0"})
    @patch("apps.ai.client.requests.post")
    def test_generate_text_success(self, mock_post):
        """Test: Erfolgreiche Text-Generierung."""
        # Mock API-Response
        mock_response = Mock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Test generierter Text"}]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        client = LLMClient()
        result = client.generate_text("Test-Prompt")

        self.assertEqual(result, "Test generierter Text")
        mock_post.assert_called_once()

    @patch.dict("os.environ", {"MOCK_LLM": "0"})
    @patch("apps.ai.client.requests.post")
    def test_generate_text_timeout(self, mock_post):
        """Test: Timeout-Fehlerbehandlung."""
        import requests

        mock_post.side_effect = requests.exceptions.Timeout()

        client = LLMClient()

        with self.assertRaises(LLMClientError) as context:
            client.generate_text("Test-Prompt")

        self.assertIsInstance(context.exception, LLMClientError)  # message is generic

    @patch.dict("os.environ", {"MOCK_LLM": "0"})
    @patch("apps.ai.client.requests.post")
    def test_generate_text_api_error(self, mock_post):
        """Test: API-Fehlerbehandlung."""
        import requests

        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        client = LLMClient()

        with self.assertRaises(LLMClientError) as context:
            client.generate_text("Test-Prompt")

        self.assertIsInstance(context.exception, LLMClientError)  # message is generic

    @override_settings(LLM_API_KEY="")
    @patch.dict("os.environ", {}, clear=True)
    def test_generate_text_no_api_key_triggers_mock(self):
        """Test: Ohne API-Key wird automatisch Mock-Modus verwendet."""
        client = LLMClient()

        result = client.generate_text("Test-Prompt")

        self.assertIn("Lesson Plan", result)


class LLMClientTailscaleOllamaTest(TestCase):
    """The self-hosted-Ollama-over-Tailscale escape hatch must stay narrow:
    only the exact configured tailnet host may skip the HTTPS/allowlist/
    port checks that protect every other provider from SSRF."""

    def setUp(self):
        self.original_key = settings.LLM_API_KEY
        self.original_base_url = settings.LLM_API_BASE_URL
        settings.LLM_API_KEY = "ollama-no-key-needed"

    def tearDown(self):
        settings.LLM_API_KEY = self.original_key
        settings.LLM_API_BASE_URL = self.original_base_url

    @patch.dict("os.environ", {"MOCK_LLM": "0", "TAILSCALE_OLLAMA_HOST": "100.78.136.85"})
    def test_plain_http_and_nonstandard_port_allowed_for_configured_tailscale_host(self):
        settings.LLM_API_BASE_URL = "http://100.78.136.85:11434/v1"
        client = LLMClient()  # must not raise
        self.assertTrue(client._is_tailscale_ollama)

    @patch.dict("os.environ", {"MOCK_LLM": "0", "TAILSCALE_OLLAMA_HOST": "100.78.136.85"})
    def test_http_still_rejected_for_a_different_host_even_with_tailscale_host_configured(self):
        settings.LLM_API_BASE_URL = "http://evil.example.com:11434/v1"
        with self.assertRaises(LLMClientError):
            LLMClient()

    @patch.dict("os.environ", {"MOCK_LLM": "0"}, clear=True)
    def test_http_rejected_when_no_tailscale_host_configured(self):
        settings.LLM_API_BASE_URL = "http://100.78.136.85:11434/v1"
        with self.assertRaises(LLMClientError):
            LLMClient()

    @patch.dict("os.environ", {"MOCK_LLM": "0", "TAILSCALE_OLLAMA_HOST": "100.78.136.85"})
    @patch("apps.ai.client.requests.post")
    def test_request_to_tailscale_host_routes_through_local_proxy(self, mock_post):
        settings.LLM_API_BASE_URL = "http://100.78.136.85:11434/v1"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_post.return_value = mock_response

        client = LLMClient()
        client.generate_text("Test-Prompt")

        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["proxies"], {"http": "http://127.0.0.1:1055", "https": "http://127.0.0.1:1055"}
        )

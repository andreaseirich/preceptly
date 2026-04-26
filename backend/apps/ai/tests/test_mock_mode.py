from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.ai.client import LLMClient


class MockLLMModeTest(TestCase):
    """Tests für den Mock-LLM-Modus."""

    @override_settings(LLM_API_KEY="demo-key")
    @patch.dict("os.environ", {"MOCK_LLM": "1"})
    @patch("apps.ai.client.requests.post")
    def test_mock_mode_activated_by_env(self, mock_post):
        client = LLMClient()

        result = client.generate_text("Generate a lesson plan about grammar rules.")

        self.assertIn("(Mock)", result)
        mock_post.assert_not_called()

    @override_settings(LLM_API_KEY="")
    @patch.dict("os.environ", {}, clear=True)
    @patch("apps.ai.client.requests.post")
    def test_mock_mode_when_api_key_missing(self, mock_post):
        client = LLMClient()

        result = client.generate_text("Generate a lesson plan about math")

        self.assertIn("(Mock)", result)
        mock_post.assert_not_called()

    @override_settings(LLM_API_KEY="demo-key")
    @patch.dict("os.environ", {}, clear=True)
    @patch("apps.ai.client.requests.post")
    def test_real_mode_uses_requests(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "Real call"}}]}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        client = LLMClient()
        result = client.generate_text("Hello world")

        self.assertEqual(result, "Real call")
        mock_post.assert_called_once()

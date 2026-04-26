import os
from unittest.mock import MagicMock, patch

from apps.ai.services import LessonPlanService
from apps.lessons.models import Lesson
from django.conf import settings
from django.test import TestCase, override_settings


from unittest import skip


@skip("Requires demo_data.json fixture not available in this environment")
class LessonPlanMockIntegrationTest(TestCase):
    fixtures = ["demo_data.json"]

    @override_settings(LLM_API_KEY="")
    @patch.dict(os.environ, {"MOCK_LLM": "1"})
    def test_generate_plan_uses_mock_sample(self):
        lesson = Lesson.objects.get(pk=1)
        service = LessonPlanService()

        lesson_plan = service.generate_lesson_plan(lesson)

        self.assertIn("Lesson Plan (Mock)", lesson_plan.content)
        self.assertEqual(lesson_plan.llm_model, settings.LLM_MODEL_NAME)

    @override_settings(LLM_API_KEY="")
    @patch.dict(os.environ, {"MOCK_LLM": "1"})
    @patch("apps.ai.services.sanitize_context")
    def test_sanitize_context_invoked_before_prompt(self, mock_sanitize):
        lesson = Lesson.objects.get(pk=1)
        mock_sanitize.side_effect = lambda ctx: {"sanitized": True, **ctx}

        service = LessonPlanService()
        service.client = MagicMock()
        service.client.generate_text.return_value = "Lesson Plan (Mock)"

        service.generate_lesson_plan(lesson)

        self.assertTrue(mock_sanitize.called)

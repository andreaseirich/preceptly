"""
Tests for the generate_lesson_plan view's extra-context handling (free-text
notes and PDF upload) added alongside the "regenerate always regenerates"
fix.
"""

import io
from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from reportlab.pdfgen import canvas

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Session


def _make_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, text)
    c.save()
    return buffer.getvalue()


class GenerateLessonPlanExtraContextTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(username="tutor", password="pass")
        UserProfile.objects.create(user=self.user, subscription_tier="pro")
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Muster",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )
        self.session = Session.objects.create(
            contract=self.contract,
            date=date.today(),
            start_time=time(14, 0),
            duration_minutes=60,
        )
        self.client.login(username="tutor", password="pass")

    def _fake_plan(self):
        return LessonPlan(
            lesson=self.session,
            contract=self.contract,
            topic="t",
            subject="s",
            content="x",
            llm_model="test-model",
        )

    @patch("apps.ai.views.LessonPlanService")
    def test_extra_notes_and_pdf_are_forwarded_to_the_service(self, mock_service_class):
        mock_service = mock_service_class.return_value
        mock_service.generate_lesson_plan.return_value = self._fake_plan()
        pdf_bytes = _make_pdf("Aufgabe: Bruchrechnung")

        self.client.post(
            reverse("ai:generate_lesson_plan", kwargs={"lesson_id": self.session.pk}),
            data={
                "extra_notes": "Bitte auf Textaufgaben eingehen",
                "extra_pdf": SimpleUploadedFile(
                    "worksheet.pdf", pdf_bytes, content_type="application/pdf"
                ),
            },
        )

        mock_service.generate_lesson_plan.assert_called_once()
        call_kwargs = mock_service.generate_lesson_plan.call_args.kwargs
        self.assertEqual(call_kwargs["extra_notes"], "Bitte auf Textaufgaben eingehen")
        self.assertIn("Aufgabe: Bruchrechnung", call_kwargs["extra_pdf_text"])

    @patch("apps.ai.views.LessonPlanService")
    def test_corrupt_pdf_upload_is_rejected_without_calling_the_service(self, mock_service_class):
        response = self.client.post(
            reverse("ai:generate_lesson_plan", kwargs={"lesson_id": self.session.pk}),
            data={
                "extra_pdf": SimpleUploadedFile(
                    "not-a-pdf.pdf", b"not a pdf", content_type="application/pdf"
                ),
            },
            follow=True,
        )

        mock_service_class.return_value.generate_lesson_plan.assert_not_called()
        self.assertContains(response, "PDF-Datei konnte nicht gelesen werden")

    @patch("apps.ai.views.LessonPlanService")
    def test_generation_works_without_any_extra_context(self, mock_service_class):
        mock_service = mock_service_class.return_value
        mock_service.generate_lesson_plan.return_value = self._fake_plan()

        self.client.post(
            reverse("ai:generate_lesson_plan", kwargs={"lesson_id": self.session.pk}),
            data={},
        )

        call_kwargs = mock_service.generate_lesson_plan.call_args.kwargs
        self.assertEqual(call_kwargs["extra_notes"], "")
        self.assertEqual(call_kwargs["extra_pdf_text"], "")

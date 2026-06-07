"""
Tests für AI-Funktionen (Premium-Gating, LessonPlan-Generierung).
"""

from datetime import date, time
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from apps.ai.client import LLMClientError
from apps.ai.prompts import build_lesson_plan_prompt, extract_subject_from_student
from apps.ai.services import LessonPlanGenerationError, LessonPlanService
from apps.ai.utils_safety import REDACTED, sanitize_context
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.core.utils import is_premium_user
from apps.lessons.models import Lesson


class PremiumGatingTest(TestCase):
    """Tests für Premium-Gating."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.premium_user = User.objects.create_user(
            username="premiumuser", email="premium@example.com", password="testpass123"
        )
        # Premium-User erstellen
        UserProfile.objects.create(user=self.premium_user, is_premium=True)

    def test_is_premium_user_false(self):
        """Test: Nicht-Premium-User wird korrekt erkannt."""
        self.assertFalse(is_premium_user(self.user))

    def test_is_premium_user_true(self):
        """Test: Premium-User wird korrekt erkannt."""
        self.assertTrue(is_premium_user(self.premium_user))

    def test_is_premium_user_creates_profile(self):
        """Test: Profile wird automatisch erstellt, falls nicht vorhanden."""
        new_user = User.objects.create_user(
            username="newuser", email="new@example.com", password="testpass123"
        )
        # Profile sollte nicht existieren
        self.assertFalse(hasattr(new_user, "profile"))
        # Nach Aufruf sollte Profile existieren
        is_premium_user(new_user)
        self.assertTrue(hasattr(new_user, "profile"))


class PromptBuildingTest(TestCase):
    """Tests für Prompt-Bau."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Set up test data."""
        self.student = self.contract = Contract.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
            grade="10. Klasse",
            subjects="Mathe, Deutsch",
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract, date=date.today(), start_time=time(14, 0), duration_minutes=60
        )

    def test_build_lesson_plan_prompt(self):
        """Test: Prompt wird korrekt gebaut."""
        safe_context = sanitize_context(
            {
                "student": {
                    "full_name": "Max Mustermann",
                    "grade": "10. Klasse",
                    "subjects": "Mathe, Deutsch",
                    "notes": "Benötigt Schwerpunkt Grammatik",
                },
                "lesson": {
                    "date": self.lesson.date.isoformat(),
                    "duration_minutes": 60,
                    "status": self.lesson.get_status_display(),
                    "notes": "Konzentriert arbeiten",
                },
                "previous_lessons": [],
            }
        )
        system_prompt, user_prompt = build_lesson_plan_prompt(self.lesson, safe_context)

        self.assertIn("Nachhilfelehrer", system_prompt)
        self.assertIn(REDACTED, user_prompt)
        self.assertIn("10. Klasse", user_prompt)
        self.assertIn("60 Minuten", user_prompt)

    def test_extract_subject_from_student(self):
        """Test: Fach wird korrekt extrahiert."""
        subject = extract_subject_from_student(self.student)
        self.assertEqual(subject, "Mathe")

        # Test mit leerem Subject
        student_no_subject = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Anna",
            last_name="Schmidt",
        )
        subject = extract_subject_from_student(student_no_subject)
        self.assertEqual(subject, "Allgemein")


class LessonPlanServiceTest(TestCase):
    """Tests für LessonPlanService mit Mock-LLM-Client."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Set up test data."""
        self.student = self.contract = Contract.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
            grade="10. Klasse",
            subjects="Mathe",
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract, date=date.today(), start_time=time(14, 0), duration_minutes=60
        )

    @patch("apps.ai.services.LLMClient")
    def test_generate_lesson_plan_success(self, mock_client_class):
        """Test: LessonPlan wird erfolgreich generiert."""
        # Mock LLM-Client
        mock_client = Mock()
        mock_client.generate_text.return_value = (
            "Test-Unterrichtsplan\n\n1. Einstieg\n2. Hauptteil\n3. Abschluss"
        )
        mock_client_class.return_value = mock_client

        service = LessonPlanService(client=mock_client)
        lesson_plan = service.generate_lesson_plan(self.lesson)

        self.assertIsNotNone(lesson_plan)
        self.assertEqual(lesson_plan.contract, self.student)
        self.assertEqual(lesson_plan.lesson, self.lesson)
        self.assertIn("Test-Unterrichtsplan", lesson_plan.content)
        mock_client.generate_text.assert_called_once()

    @patch("apps.ai.services.LLMClient")
    def test_generate_lesson_plan_api_error(self, mock_client_class):
        """Test: Fehlerbehandlung bei API-Fehler."""
        # Mock LLM-Client mit Fehler
        mock_client = Mock()
        mock_client.generate_text.side_effect = LLMClientError("API-Fehler")
        mock_client_class.return_value = mock_client

        service = LessonPlanService(client=mock_client)

        with self.assertRaises(LessonPlanGenerationError):
            service.generate_lesson_plan(self.lesson)

    def test_gather_context(self):
        """Test: Kontext wird korrekt gesammelt."""
        service = LessonPlanService()
        context = service.gather_context(self.lesson)

        self.assertIn("previous_lessons", context)
        self.assertIn("student", context)
        self.assertIn("lesson", context)
        self.assertEqual(context["lesson"]["duration_minutes"], 60)

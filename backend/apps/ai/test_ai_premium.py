"""
Tests für AI-Funktionen (Premium-Gating, LessonPlan-Generierung).
"""

from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.ai.client import LLMClientError, LLMServiceUnavailableError
from apps.ai.prompts import build_lesson_plan_prompt, extract_subject_from_student
from apps.ai.services import LessonPlanGenerationError, LessonPlanService
from apps.ai.utils_safety import REDACTED, sanitize_context
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.core.utils import is_premium_user
from apps.lesson_plans.models import LessonPlan
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
        UserProfile.objects.create(user=self.premium_user, subscription_tier="pro")

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

    def test_build_lesson_plan_prompt_includes_extra_notes_and_pdf_text(self):
        """The tutor can supply extra context before generating (free text
        and/or text extracted from an uploaded PDF) - both must reach the
        prompt, clearly wrapped as untrusted data."""
        safe_context = sanitize_context({"student": {}, "lesson": {}, "previous_lessons": []})

        _, user_prompt = build_lesson_plan_prompt(
            self.lesson,
            safe_context,
            extra_notes="Fokus auf Bruchrechnung",
            extra_pdf_text="Aufgabe 3: Kürze 12/18",
        )

        self.assertIn("Fokus auf Bruchrechnung", user_prompt)
        self.assertIn("Aufgabe 3: Kürze 12/18", user_prompt)
        self.assertIn("<user_provided_untrusted>", user_prompt)

    def test_build_lesson_plan_prompt_without_extra_context_unchanged(self):
        """No extra_notes/extra_pdf_text supplied must not add empty
        sections to the prompt."""
        safe_context = sanitize_context({"student": {}, "lesson": {}, "previous_lessons": []})

        _, user_prompt = build_lesson_plan_prompt(self.lesson, safe_context)

        self.assertNotIn("Zusätzliche Hinweise", user_prompt)
        self.assertNotIn("Material aus hochgeladenem PDF", user_prompt)

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
        lesson_plan = service.generate_lesson_plan(self.lesson, user=self.user)

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
            service.generate_lesson_plan(self.lesson, user=self.user)

    def test_gather_context(self):
        """Test: Kontext wird korrekt gesammelt."""
        service = LessonPlanService()
        context = service.gather_context(self.lesson)

        self.assertIn("previous_lessons", context)
        self.assertIn("student", context)
        self.assertIn("lesson", context)
        self.assertEqual(context["lesson"]["duration_minutes"], 60)

    @patch("apps.ai.services.LLMClient")
    def test_generate_lesson_plan_shows_unreachable_message_not_generic_error(
        self, mock_client_class
    ):
        """Regression: a self-hosted provider (e.g. Ollama over Tailscale)
        being offline must surface a clear "try again later" message, not
        the generic "something went wrong" text used for other failures -
        the two situations need different user reactions (wait vs. report
        a bug)."""
        mock_client = Mock()
        mock_client.generate_text.side_effect = LLMServiceUnavailableError("connection failed")
        mock_client_class.return_value = mock_client

        service = LessonPlanService(client=mock_client)

        with self.assertRaises(LessonPlanGenerationError) as ctx:
            service.generate_lesson_plan(self.lesson, user=self.user)

        self.assertIn("nicht erreichbar", str(ctx.exception))

    @patch("apps.ai.services.LLMClient")
    def test_regenerate_creates_a_fresh_plan_not_the_stale_one(self, mock_client_class):
        """Regression: clicking "regenerate" on an already-completed plan
        must actually call the AI again, not silently hand back the exact
        same plan it made the first time."""
        mock_client = Mock()
        mock_client.generate_text.side_effect = ["Erster Plan", "Zweiter Plan"]
        mock_client_class.return_value = mock_client

        service = LessonPlanService(client=mock_client)
        first = service.generate_lesson_plan(self.lesson, user=self.user)
        second = service.generate_lesson_plan(self.lesson, user=self.user)

        self.assertEqual(mock_client.generate_text.call_count, 2)
        self.assertNotEqual(first.pk, second.pk)
        self.assertIn("Erster Plan", first.content)
        self.assertIn("Zweiter Plan", second.content)

    @patch("apps.ai.services.LLMClient")
    def test_concurrent_call_does_not_start_a_second_generation(self, mock_client_class):
        """A generation already running (content="" placeholder, created
        just now) for this lesson must not be raced by a second call -
        e.g. a double form submit."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        in_progress = LessonPlan.objects.create(
            lesson=self.lesson,
            contract=self.student,
            topic="Wird gerade erstellt",
            subject="Mathe",
            content="",
        )

        service = LessonPlanService(client=mock_client)
        result = service.generate_lesson_plan(self.lesson, user=self.user)

        mock_client.generate_text.assert_not_called()
        self.assertEqual(result.pk, in_progress.pk)

    @patch("apps.ai.services.LLMClient")
    def test_stale_in_progress_placeholder_is_discarded(self, mock_client_class):
        """A placeholder left behind by a request that died mid-flight
        (gateway timeout, worker restart) before it could fill in the
        content or clean up after itself must not block generation
        forever - once it's older than the LLM call's own timeout window,
        a fresh attempt must go ahead."""
        mock_client = Mock()
        mock_client.generate_text.return_value = "Neuer Plan"
        mock_client_class.return_value = mock_client
        stale = LessonPlan.objects.create(
            lesson=self.lesson,
            contract=self.student,
            topic="Wird gerade erstellt",
            subject="Mathe",
            content="",
        )
        LessonPlan.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )

        service = LessonPlanService(client=mock_client)
        result = service.generate_lesson_plan(self.lesson, user=self.user)

        mock_client.generate_text.assert_called_once()
        self.assertNotEqual(result.pk, stale.pk)
        self.assertIn("Neuer Plan", result.content)
        self.assertFalse(LessonPlan.objects.filter(pk=stale.pk).exists())

    @patch("apps.ai.services.LLMClient")
    def test_extra_notes_and_pdf_text_reach_the_prompt_sent_to_the_llm(self, mock_client_class):
        mock_client = Mock()
        mock_client.generate_text.return_value = "Plan"
        mock_client_class.return_value = mock_client

        service = LessonPlanService(client=mock_client)
        service.generate_lesson_plan(
            self.lesson,
            user=self.user,
            extra_notes="Schüler braucht mehr Übung bei Textaufgaben",
            extra_pdf_text="Arbeitsblatt: Prozentrechnung",
        )

        sent_prompt = mock_client.generate_text.call_args.kwargs["prompt"]
        self.assertIn("Schüler braucht mehr Übung bei Textaufgaben", sent_prompt)
        self.assertIn("Arbeitsblatt: Prozentrechnung", sent_prompt)

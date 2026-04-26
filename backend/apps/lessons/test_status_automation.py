"""
Tests für automatische Status-Setzung bei Recurring Lessons und manueller Erstellung.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_service import RecurringLessonService
from apps.lessons.status_service import LessonStatusService
from apps.students.models import Student


class RecurringLessonStatusAutomationTest(TestCase):
    """Tests für automatische Status-Setzung bei Recurring Lessons."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Max", last_name="Mustermann", email="max@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_recurring_lessons_past_get_taught_status(self):
        """Test: Serientermine erzeugen Lessons in Vergangenheit → Status TAUGHT."""
        past_date = timezone.localdate() - timedelta(days=10)

        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=past_date,
            end_date=past_date + timedelta(days=7),
            start_time=time(14, 0),
            duration_minutes=60,
            monday=True,
        )

        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        self.assertGreater(result["created"], 0)

        # Prüfe, dass vergangene Lessons Status TAUGHT haben
        lessons = Lesson.objects.filter(contract=self.contract)
        for lesson in lessons:
            if lesson.date < timezone.localdate():
                self.assertEqual(
                    lesson.status, "taught", f"Lesson am {lesson.date} sollte Status TAUGHT haben"
                )

    def test_recurring_lessons_future_get_planned_status(self):
        """Test: Serientermine erzeugen Lessons in Zukunft → Status PLANNED."""
        future_date = timezone.localdate() + timedelta(days=10)

        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=future_date,
            end_date=future_date + timedelta(days=7),
            start_time=time(14, 0),
            duration_minutes=60,
            monday=True,
        )

        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        self.assertGreater(result["created"], 0)

        # Prüfe, dass zukünftige Lessons Status PLANNED haben
        lessons = Lesson.objects.filter(contract=self.contract)
        for lesson in lessons:
            if lesson.date >= timezone.localdate():
                self.assertEqual(
                    lesson.status, "planned", f"Lesson am {lesson.date} sollte Status PLANNED haben"
                )

    def test_recurring_lessons_mixed_past_and_future(self):
        """Test: Serie mit vergangenen und zukünftigen Lessons → korrekte Status-Verteilung."""
        today = timezone.localdate()
        past_date = today - timedelta(days=5)
        future_date = today + timedelta(days=5)

        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=past_date,
            end_date=future_date,
            start_time=time(14, 0),
            duration_minutes=60,
            monday=True,
            wednesday=True,
        )

        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        self.assertGreater(result["created"], 0)

        # Prüfe Status-Verteilung
        lessons = Lesson.objects.filter(contract=self.contract)
        past_lessons = [lesson for lesson in lessons if lesson.date < today]
        future_lessons = [lesson for lesson in lessons if lesson.date >= today]

        # Vergangene sollten TAUGHT sein
        for lesson in past_lessons:
            self.assertEqual(
                lesson.status, "taught", f"Vergangene Lesson am {lesson.date} sollte TAUGHT sein"
            )

        # Zukünftige sollten PLANNED sein
        for lesson in future_lessons:
            self.assertEqual(
                lesson.status, "planned", f"Zukünftige Lesson am {lesson.date} sollte PLANNED sein"
            )


class ManualLessonStatusAutomationTest(TestCase):
    """Tests für automatische Status-Setzung bei manueller Lesson-Erstellung."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Lisa", last_name="Müller", email="lisa@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_manual_lesson_past_gets_taught_status(self):
        """Test: Manuell erstellte Lesson in Vergangenheit → Status TAUGHT."""
        past_date = timezone.localdate() - timedelta(days=5)

        lesson = Lesson(
            contract=self.contract,
            date=past_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="",  # Leer - wird automatisch gesetzt
        )

        # Status setzen (vor dem Speichern)
        LessonStatusService.update_status_for_lesson(lesson)
        lesson.save()
        # Nochmal setzen nach Speichern (falls nötig)
        LessonStatusService.update_status_for_lesson(lesson)

        self.assertEqual(lesson.status, "taught")

    def test_manual_lesson_future_gets_planned_status(self):
        """Test: Manuell erstellte Lesson in Zukunft → Status PLANNED."""
        future_date = timezone.localdate() + timedelta(days=5)

        lesson = Lesson(
            contract=self.contract,
            date=future_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="",  # Leer - wird automatisch gesetzt
        )

        # Status setzen (vor dem Speichern)
        LessonStatusService.update_status_for_lesson(lesson)
        lesson.save()
        # Nochmal setzen nach Speichern (falls nötig)
        LessonStatusService.update_status_for_lesson(lesson)

        self.assertEqual(lesson.status, "planned")

    def test_lesson_form_does_not_include_status_field(self):
        """Test: LessonForm enthält kein Status-Feld mehr."""
        from apps.lessons.forms import LessonForm

        form = LessonForm()

        # Status sollte NICHT in den Feldern sein
        self.assertNotIn("status", form.fields)

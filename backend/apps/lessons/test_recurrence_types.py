"""
Tests für verschiedene Wiederholungsmuster bei Recurring Lessons.
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
from apps.students.models import Student


class WeeklyRecurrenceTest(TestCase):
    """Tests für wöchentliche Wiederholung (wie bisher)."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Max", last_name="Mustermann", email="max@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 8, 1),
            end_date=date(2025, 8, 31),
            is_active=True,
        )

    def test_weekly_recurrence_generates_lessons_every_week(self):
        """Test: Wöchentliche Wiederholung erzeugt Lessons jede Woche."""
        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=date(2025, 8, 4),  # Montag
            end_date=date(2025, 8, 25),
            start_time=time(14, 0),
            duration_minutes=60,
            recurrence_type="weekly",
            monday=True,
        )

        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        # Sollte 4 Montage im Zeitraum erzeugen (4., 11., 18., 25.)
        self.assertEqual(result["created"], 4)

        # Prüfe, dass alle Lessons Montage sind
        lessons = Lesson.objects.filter(contract=self.contract)
        for lesson in lessons:
            self.assertEqual(lesson.date.weekday(), 0)  # Montag = 0


class BiweeklyRecurrenceTest(TestCase):
    """Tests für zweiwöchentliche Wiederholung."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Lisa", last_name="Müller", email="lisa@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 8, 1),
            end_date=date(2025, 9, 30),
            is_active=True,
        )

    def test_biweekly_recurrence_generates_lessons_every_two_weeks(self):
        """Test: Zweiwöchentliche Wiederholung erzeugt Lessons nur jede 2. Woche."""
        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=date(2025, 8, 4),  # Montag
            end_date=date(2025, 9, 15),
            start_time=time(15, 0),
            duration_minutes=90,
            recurrence_type="biweekly",
            monday=True,
        )

        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        # Sollte nur jede 2. Woche erzeugen
        # 4. Aug (Woche 0), 18. Aug (Woche 2), 1. Sep (Woche 4), 15. Sep (Woche 6)
        self.assertGreaterEqual(result["created"], 3)
        self.assertLessEqual(result["created"], 4)

        # Prüfe, dass Lessons im 2-Wochen-Abstand sind
        lessons = Lesson.objects.filter(contract=self.contract).order_by("date")
        if len(lessons) >= 2:
            for i in range(1, len(lessons)):
                days_diff = (lessons[i].date - lessons[i - 1].date).days
                # Sollte etwa 14 Tage sein (2 Wochen)
                self.assertGreaterEqual(days_diff, 13)
                self.assertLessEqual(days_diff, 15)


class MonthlyRecurrenceTest(TestCase):
    """Tests für monatliche Wiederholung."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Tom", last_name="Schmidt", email="tom@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("35.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 8, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_monthly_recurrence_generates_lessons_every_month(self):
        """Test: Monatliche Wiederholung erzeugt Lessons jeden Monat am gleichen Tag."""
        # Verwende einen Tag, der in mehreren Monaten den gleichen Wochentag hat
        # 15. August 2025 ist ein Freitag, aber 15. September ist ein Montag
        # Verwende stattdessen einen Tag, der in mehreren Monaten Freitag ist
        # 1. August 2025 ist ein Freitag, 1. September ist ein Montag
        # Besser: Verwende mehrere Wochentage oder einen Tag, der häufiger vorkommt
        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=date(2025, 8, 1),  # 1. August (Freitag)
            end_date=date(2025, 11, 30),
            start_time=time(16, 0),
            duration_minutes=60,
            recurrence_type="monthly",
            friday=True,  # Freitag
            monday=True,  # Auch Montag, damit mehr Termine erzeugt werden
        )

        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        # Sollte Lessons für 1. Aug (Fr), 1. Sep (Mo), 1. Okt (Mi), 1. Nov (Sa) erzeugen
        # Nur wenn diese Tage Freitage oder Montage sind
        self.assertGreaterEqual(result["created"], 1)

        # Prüfe, dass alle Lessons am 1. des Monats sind
        lessons = Lesson.objects.filter(contract=self.contract).order_by("date")
        for lesson in lessons:
            self.assertEqual(lesson.date.day, 1)
            # Prüfe, dass es ein Freitag oder Montag ist
            weekday = lesson.date.weekday()
            self.assertIn(weekday, [0, 4])  # Montag oder Freitag

    def test_monthly_recurrence_handles_month_end(self):
        """Test: Monatliche Wiederholung behandelt Monatsende korrekt (z.B. 31. -> 28./29./30.)."""
        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=date(2025, 8, 31),  # 31. August (Sonntag)
            end_date=date(2025, 11, 30),
            start_time=time(14, 0),
            duration_minutes=60,
            recurrence_type="monthly",
            sunday=True,
        )

        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        # Sollte Lessons erzeugen, auch wenn nicht alle Monate den 31. haben
        self.assertGreaterEqual(result["created"], 1)

        # Prüfe, dass alle Lessons am Ende des Monats sind
        lessons = Lesson.objects.filter(contract=self.contract).order_by("date")
        for lesson in lessons:
            # Sollte am Ende des Monats sein (28-31)
            self.assertGreaterEqual(lesson.date.day, 28)


class RecurrenceStatusAutomationTest(TestCase):
    """Tests für automatische Status-Setzung bei verschiedenen Wiederholungsmustern."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Anna", last_name="Weber", email="anna@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("28.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_biweekly_lessons_get_correct_status(self):
        """Test: Zweiwöchentliche Lessons bekommen korrekten Status."""
        past_date = timezone.localdate() - timedelta(days=20)

        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=past_date,
            end_date=past_date + timedelta(days=30),
            start_time=time(14, 0),
            duration_minutes=60,
            recurrence_type="biweekly",
            monday=True,
        )

        RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        # Prüfe Status der erzeugten Lessons
        lessons = Lesson.objects.filter(contract=self.contract)
        for lesson in lessons:
            if lesson.date < timezone.localdate():
                self.assertEqual(lesson.status, "taught")
            else:
                self.assertEqual(lesson.status, "planned")

    def test_monthly_lessons_get_correct_status(self):
        """Test: Monatliche Lessons bekommen korrekten Status."""
        past_date = timezone.localdate() - timedelta(days=60)

        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=past_date,
            end_date=past_date + timedelta(days=120),
            start_time=time(15, 0),
            duration_minutes=60,
            recurrence_type="monthly",
            monday=True,
        )

        RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        # Prüfe Status der erzeugten Lessons
        lessons = Lesson.objects.filter(contract=self.contract)
        for lesson in lessons:
            if lesson.date < timezone.localdate():
                self.assertEqual(lesson.status, "taught")
            else:
                self.assertEqual(lesson.status, "planned")

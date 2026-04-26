"""
Tests für Lesson-Services (Konfliktprüfung, Abfragen).
"""

from datetime import date, datetime, time
from decimal import Decimal

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService, LessonQueryService
from apps.students.models import Student
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User


class LessonConflictServiceTest(TestCase):
    """Tests für Konfliktprüfung."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Set up test data."""
        self.student1 = Student.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
        )
        self.student2 = Student.objects.create(
            user=self.user,
            first_name="Anna",
            last_name="Schmidt",
        )
        self.contract1 = Contract.objects.create(
            student=self.student1, hourly_rate=Decimal("25.00"), start_date=date.today()
        )
        self.contract2 = Contract.objects.create(
            student=self.student2, hourly_rate=Decimal("30.00"), start_date=date.today()
        )

    def test_calculate_time_block(self):
        """Test: Zeitblock-Berechnung inkl. Fahrtzeiten."""
        lesson = Lesson.objects.create(
            contract=self.contract1,
            date=date.today(),
            start_time=time(14, 0),
            duration_minutes=60,
            travel_time_before_minutes=15,
            travel_time_after_minutes=20,
        )

        start, end = LessonConflictService.calculate_time_block(lesson)

        # Start sollte 15 Minuten vor 14:00 sein
        expected_start = timezone.make_aware(datetime.combine(date.today(), time(13, 45)))
        # Ende sollte 14:00 + 60 + 20 = 15:20 sein
        expected_end = timezone.make_aware(datetime.combine(date.today(), time(15, 20)))

        self.assertEqual(start, expected_start)
        self.assertEqual(end, expected_end)

    def test_no_conflicts(self):
        """Test: Keine Konflikte bei nicht überlappenden Lessons."""
        lesson1 = Lesson.objects.create(
            contract=self.contract1, date=date.today(), start_time=time(14, 0), duration_minutes=60
        )
        Lesson.objects.create(
            contract=self.contract2,
            date=date.today(),
            start_time=time(16, 0),  # 2 Stunden später, keine Überschneidung
            duration_minutes=60,
        )

        conflicts = LessonConflictService.check_conflicts(lesson1)
        self.assertEqual(len(conflicts), 0)

    def test_lesson_conflict(self):
        """Test: Konflikt zwischen zwei Lessons."""
        lesson1 = Lesson.objects.create(
            contract=self.contract1, date=date.today(), start_time=time(14, 0), duration_minutes=60
        )
        Lesson.objects.create(
            contract=self.contract2,
            date=date.today(),
            start_time=time(14, 30),  # Überschneidung!
            duration_minutes=60,
        )

        conflicts = LessonConflictService.check_conflicts(lesson1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "lesson")

    def test_blocked_time_conflict(self):
        """Test: Konflikt mit Blockzeit."""
        lesson = Lesson.objects.create(
            contract=self.contract1, date=date.today(), start_time=time(14, 0), duration_minutes=60
        )

        # Blockzeit, die mit Lesson überlappt
        BlockedTime.objects.create(
            user=self.user,
            title="Uni-Vorlesung",
            start_datetime=timezone.make_aware(datetime.combine(date.today(), time(14, 30))),
            end_datetime=timezone.make_aware(datetime.combine(date.today(), time(16, 0))),
        )

        conflicts = LessonConflictService.check_conflicts(lesson)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "blocked_time")

    def test_conflict_with_travel_time(self):
        """Test: Konflikt durch Fahrtzeiten."""
        lesson1 = Lesson.objects.create(
            contract=self.contract1,
            date=date.today(),
            start_time=time(14, 0),
            duration_minutes=60,
            travel_time_after_minutes=30,  # Endet um 15:30
        )
        Lesson.objects.create(
            contract=self.contract2,
            date=date.today(),
            start_time=time(15, 0),  # Startet um 15:00, Überschneidung!
            duration_minutes=60,
        )

        conflicts = LessonConflictService.check_conflicts(lesson1)
        self.assertEqual(len(conflicts), 1)


class LessonQueryServiceTest(TestCase):
    """Tests für Lesson-Abfragen."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Set up test data."""
        self.student = Student.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
        )
        self.contract = Contract.objects.create(
            student=self.student, hourly_rate=Decimal("25.00"), start_date=date(2025, 12, 1)
        )

    def test_get_lessons_for_month(self):
        """Test: Lessons für einen Monat abrufen."""
        # Lesson im Dezember 2025
        lesson1 = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 12, 5),
            start_time=time(14, 0),
            duration_minutes=60,
        )
        # Lesson im November 2025 (sollte nicht erscheinen)
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 11, 30),
            start_time=time(14, 0),
            duration_minutes=60,
        )

        lessons = LessonQueryService.get_lessons_for_month(2025, 12)
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0], lesson1)

    def test_get_today_lessons(self):
        """Test: Heutige Lessons abrufen."""
        today = timezone.now().date()
        lesson = Lesson.objects.create(
            contract=self.contract, date=today, start_time=time(14, 0), duration_minutes=60
        )

        lessons = LessonQueryService.get_today_lessons()
        self.assertIn(lesson, lessons)

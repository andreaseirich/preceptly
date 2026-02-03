from datetime import date, time
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.test import TestCase


class LessonModelTest(TestCase):
    """Tests für das Lesson-Model."""

    def setUp(self):
        """Set up test data."""
        self.student = Student.objects.create(first_name="Max", last_name="Mustermann")
        self.contract = Contract.objects.create(
            student=self.student, hourly_rate=Decimal("25.00"), start_date=date.today()
        )

    def test_create_lesson(self):
        """Test: Lesson kann erstellt werden."""
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date.today(),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )
        self.assertEqual(lesson.contract, self.contract)
        self.assertEqual(lesson.status, "planned")
        self.assertEqual(lesson.total_time_minutes, 60)

    def test_lesson_with_travel_time(self):
        """Test: Lesson mit Fahrtzeiten."""
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date.today(),
            start_time=time(14, 0),
            duration_minutes=60,
            travel_time_before_minutes=15,
            travel_time_after_minutes=20,
        )
        self.assertEqual(lesson.total_time_minutes, 95)  # 60 + 15 + 20

    def test_lesson_status_choices(self):
        """Test: Lesson-Status-Auswahl."""
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date.today(),
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )
        self.assertEqual(lesson.get_status_display(), "Ausgezahlt")

    def test_lesson_relationship_to_contract(self):
        """Test: Beziehung zwischen Lesson und Contract."""
        lesson = Lesson.objects.create(
            contract=self.contract, date=date.today(), start_time=time(14, 0), duration_minutes=60
        )
        self.assertEqual(self.contract.sessions.first(), lesson)

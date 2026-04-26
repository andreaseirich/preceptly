"""
Tests for recurrence options in week view lesson creation.
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.students.models import Student


class RecurrenceInWeekViewTest(TestCase):
    """Tests for creating lessons with recurrence options in week view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client.login(username="testuser", password="password")

        self.student = Student.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2023, 1, 1),
        )

    def test_create_single_lesson_without_recurrence(self):
        """Test: Creating a single lesson without recurrence creates exactly one lesson."""
        response = self.client.post(
            reverse("lessons:create"),
            {
                "contract": self.contract.pk,
                "date": "2023-01-15",
                "start_time": "14:00",
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
                "notes": "",
                "is_recurring": False,
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirect after creation
        self.assertEqual(Lesson.objects.count(), 1)
        self.assertEqual(RecurringLesson.objects.count(), 0)

        lesson = Lesson.objects.first()
        self.assertEqual(lesson.date, date(2023, 1, 15))
        self.assertEqual(lesson.start_time, time(14, 0))

    def test_create_lesson_with_weekly_recurrence(self):
        """Test: Creating a lesson with weekly recurrence creates RecurringLesson and multiple lessons."""
        response = self.client.post(
            reverse("lessons:create"),
            {
                "contract": self.contract.pk,
                "date": "2023-01-15",  # Sunday
                "start_time": "14:00",
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
                "notes": "",
                "is_recurring": True,
                "recurrence_type": "weekly",
                "recurrence_end_date": "2023-01-29",  # 2 weeks later
                "recurrence_weekdays": ["0"],  # Monday
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirect after creation
        self.assertEqual(RecurringLesson.objects.count(), 1)

        recurring = RecurringLesson.objects.first()
        self.assertEqual(recurring.recurrence_type, "weekly")
        self.assertTrue(recurring.monday)

        # Check that lessons were generated
        # Should generate lessons for Mondays in the period (Jan 16, Jan 23)
        generated_lessons = Lesson.objects.filter(
            contract=self.contract, date__gte=date(2023, 1, 15), date__lte=date(2023, 1, 29)
        )
        self.assertGreaterEqual(generated_lessons.count(), 2)

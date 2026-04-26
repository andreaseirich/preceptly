"""
Tests for recurrence weekday selection functionality.
"""

from datetime import date, time
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class RecurrenceWeekdaysTest(TestCase):
    """Tests for recurrence weekday selection."""

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

    def test_weekday_selection_in_form(self):
        """Test: Weekday checkboxes are visible and functional in form."""
        response = self.client.get(reverse("lessons:create"))

        self.assertEqual(response.status_code, 200)
        # Check that weekday checkboxes are present
        self.assertContains(response, "recurrence_weekdays")
        # Check that Monday checkbox exists
        self.assertContains(response, "Monday")
        # Check that weekdays container exists
        self.assertContains(response, "weekdays-container")

    def test_recurring_lesson_with_weekdays_monday_wednesday(self):
        """Test: Recurring lesson with Monday and Wednesday creates lessons only on Mo+We."""
        # Create a recurring lesson starting on a Monday (2023-01-02 is a Monday)
        start_date = date(2023, 1, 2)  # Monday
        end_date = date(2023, 1, 16)  # 2 weeks later

        form_data = {
            "contract": self.contract.pk,
            "date": start_date,
            "start_time": time(14, 0),
            "duration_minutes": 60,
            "travel_time_before_minutes": 0,
            "travel_time_after_minutes": 0,
            "notes": "",
            "is_recurring": True,
            "recurrence_type": "weekly",
            "recurrence_end_date": end_date,
            "recurrence_weekdays": ["0", "2"],  # Monday and Wednesday
        }

        response = self.client.post(reverse("lessons:create"), form_data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that RecurringLesson was created
        recurring_lessons = RecurringLesson.objects.filter(contract=self.contract)
        self.assertEqual(recurring_lessons.count(), 1)

        recurring = recurring_lessons.first()
        self.assertTrue(recurring.monday)
        self.assertFalse(recurring.tuesday)
        self.assertTrue(recurring.wednesday)
        self.assertFalse(recurring.thursday)
        self.assertFalse(recurring.friday)
        self.assertFalse(recurring.saturday)
        self.assertFalse(recurring.sunday)

        # Check that lessons were generated only on Monday and Wednesday
        lessons = Lesson.objects.filter(contract=self.contract).order_by("date")
        self.assertGreater(lessons.count(), 0)

        # All lessons should be on Monday (0) or Wednesday (2)
        for lesson in lessons:
            weekday = lesson.date.weekday()  # 0=Monday, 2=Wednesday
            self.assertIn(weekday, [0, 2], f"Lesson on {lesson.date} should be Monday or Wednesday")

    def test_recurring_lesson_requires_weekdays(self):
        """Test: Recurring lesson without weekdays shows error."""
        start_date = date(2023, 1, 2)
        end_date = date(2023, 1, 16)

        form_data = {
            "contract": self.contract.pk,
            "date": start_date,
            "start_time": time(14, 0),
            "duration_minutes": 60,
            "travel_time_before_minutes": 0,
            "travel_time_after_minutes": 0,
            "notes": "",
            "is_recurring": True,
            "recurrence_type": "weekly",
            "recurrence_end_date": end_date,
            # recurrence_weekdays is not included (empty list)
        }

        response = self.client.post(reverse("lessons:create"), form_data)

        # Should show form with error (form validation fails)
        self.assertEqual(response.status_code, 200)
        # Check for form errors (Django forms show errors in the form)
        # The error should be in the form's error list
        self.assertContains(
            response, "is_recurring", status_code=200
        )  # Form is re-rendered with errors

        # No RecurringLesson should be created
        self.assertEqual(RecurringLesson.objects.count(), 0)

    def test_weekday_values_in_post_request(self):
        """Test: Weekday values are correctly bound in POST request."""
        start_date = date(2023, 1, 2)
        end_date = date(2023, 1, 16)

        form_data = {
            "contract": self.contract.pk,
            "date": start_date,
            "start_time": time(14, 0),
            "duration_minutes": 60,
            "travel_time_before_minutes": 0,
            "travel_time_after_minutes": 0,
            "notes": "",
            "is_recurring": True,
            "recurrence_type": "weekly",
            "recurrence_end_date": end_date,
            "recurrence_weekdays": ["1", "3", "5"],  # Tuesday, Thursday, Saturday
        }

        response = self.client.post(reverse("lessons:create"), form_data)

        # Should succeed
        self.assertEqual(response.status_code, 302)

        # Check that RecurringLesson has correct weekdays
        recurring = RecurringLesson.objects.filter(contract=self.contract).first()
        self.assertIsNotNone(recurring)
        self.assertFalse(recurring.monday)
        self.assertTrue(recurring.tuesday)
        self.assertFalse(recurring.wednesday)
        self.assertTrue(recurring.thursday)
        self.assertFalse(recurring.friday)
        self.assertTrue(recurring.saturday)
        self.assertFalse(recurring.sunday)

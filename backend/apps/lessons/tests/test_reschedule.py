"""
Regression test for LessonRescheduleView: reschedule must not 500.
"""

from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson


class LessonRescheduleViewTest(TestCase):
    """Rescheduling a lesson (e.g. one hour later) must succeed, not 500."""

    def setUp(self):
        self.client = Client()
        self.tutor = User.objects.create_user(username="tutor", password="test")
        self.client.force_login(self.tutor)
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Test",
            last_name="Student",
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

    def test_reschedule_one_hour_later_succeeds(self):
        """Shifting a lesson by one hour later must redirect, not raise a 500."""
        new_date = self.lesson.date
        new_time = time(11, 0)
        response = self.client.post(
            reverse("lessons:reschedule", args=[self.lesson.pk]),
            {"date": new_date.isoformat(), "start_time": new_time.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.start_time, new_time)
        self.assertIsNone(self.lesson.recurring_session)

    def test_reschedule_clears_recurring_session_link(self):
        """Rescheduling detaches the lesson from its recurring series."""
        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=date.today(),
            start_time=time(10, 0),
            duration_minutes=60,
            monday=True,
        )
        self.lesson.recurring_session = recurring
        self.lesson.save(update_fields=["recurring_session"])

        response = self.client.post(
            reverse("lessons:reschedule", args=[self.lesson.pk]),
            {
                "date": self.lesson.date.isoformat(),
                "start_time": time(11, 0).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.lesson.refresh_from_db()
        self.assertIsNone(self.lesson.recurring_session)

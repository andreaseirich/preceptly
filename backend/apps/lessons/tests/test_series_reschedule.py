"""
Tests for series reschedule (edit entire series) in LessonUpdateView.
"""

import re
from datetime import date, time
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_service import RecurringLessonService
from apps.lessons.recurring_utils import get_all_lessons_for_recurring
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class SeriesRescheduleTest(TestCase):
    """Test that editing a lesson with scope=series updates the entire series."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.student = Student.objects.create(user=self.user, first_name="Max", last_name="Test")
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
            is_active=True,
        )
        self.recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=date(2025, 1, 6),
            end_date=date(2025, 1, 31),
            start_time=time(10, 0),
            duration_minutes=60,
            monday=True,
            wednesday=True,
            recurrence_type="weekly",
            is_active=True,
        )
        result = RecurringLessonService.generate_lessons(self.recurring, check_conflicts=False)
        self.assertGreater(result["created"], 0)
        self.client = Client()
        self.client.login(username="tutor", password="test")

    def test_series_reschedule_updates_all_instances(self):
        """Edit entire series: start_time change propagates to all lessons."""
        all_lessons = get_all_lessons_for_recurring(self.recurring)
        self.assertGreaterEqual(len(all_lessons), 2)
        lesson = all_lessons[0]

        url = reverse("lessons:update", kwargs={"pk": lesson.pk})
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)
        match = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            get_resp.content.decode(),
        )
        csrf = match.group(1) if match else ""

        response = self.client.post(
            url,
            data={
                "csrfmiddlewaretoken": csrf,
                "contract": self.contract.id,
                "date": lesson.date.strftime("%Y-%m-%d"),
                "start_time": "14:00",
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
                "notes": "",
                "edit_scope": "series",
                "recurrence_weekdays": ["0", "2"],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.recurring.refresh_from_db()
        self.assertEqual(self.recurring.start_time, time(14, 0))

        for les in get_all_lessons_for_recurring(self.recurring):
            self.assertEqual(les.start_time, time(14, 0))

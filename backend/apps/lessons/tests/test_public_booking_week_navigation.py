"""
Tests for Public Booking week navigation: drift fix and week param.
"""

import json
from datetime import date

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.booking_service import BookingService
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase


class PublicBookingWeekNavigationTest(TestCase):
    """Test week API stability and week= param for public booking."""

    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="test")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.tutor)
        self.profile.public_booking_token = "tok-nav"
        self.profile.default_working_hours = {"monday": [{"start": "09:00", "end": "17:00"}]}
        self.profile.save()
        self.student = Student.objects.create(user=self.tutor, first_name="A", last_name="B")
        Contract.objects.create(
            student=self.student,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        self.client = Client()
        self.week_url = "/lessons/public-booking/tok-nav/week/"

    def _get_week_via_param(self, week_iso):
        return self.client.get(self.week_url, {"week": week_iso})

    def _get_week_via_ymd(self, year, month, day):
        return self.client.get(self.week_url, {"year": year, "month": month, "day": day})

    def test_week_param_returns_correct_week_start(self):
        """Week API accepts ?week=YYYY-MM-DD and returns that Monday's week."""
        resp = self._get_week_via_param("2025-01-06")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["week_data"]["week_start"], "2025-01-06")
        self.assertEqual(data["week_data"]["week_end"], "2025-01-12")

    def test_next_then_prev_returns_same_week_start(self):
        """Navigating next then prev returns to exact same week (no drift)."""
        base = "2025-01-06"
        resp1 = self._get_week_via_param(base)
        self.assertEqual(resp1.status_code, 200)
        week_start_1 = json.loads(resp1.content)["week_data"]["week_start"]

        next_week = "2025-01-13"
        resp2 = self._get_week_via_param(next_week)
        self.assertEqual(resp2.status_code, 200)
        week_start_2 = json.loads(resp2.content)["week_data"]["week_start"]
        self.assertEqual(week_start_2, "2025-01-13")

        prev_week = "2025-01-06"
        resp3 = self._get_week_via_param(prev_week)
        self.assertEqual(resp3.status_code, 200)
        week_start_3 = json.loads(resp3.content)["week_data"]["week_start"]
        self.assertEqual(week_start_3, week_start_1)
        self.assertEqual(week_start_3, "2025-01-06")

    def test_week_boundaries_monday_based(self):
        """Week start is always Monday; weekday(0)=Monday in Python."""
        for y, m, d, expected_monday in [
            (2025, 1, 6, "2025-01-06"),
            (2025, 1, 8, "2025-01-06"),
            (2025, 1, 12, "2025-01-06"),
            (2025, 1, 13, "2025-01-13"),
            (2024, 12, 30, "2024-12-30"),
        ]:
            data = BookingService.get_public_booking_data(y, m, d, user=self.tutor)
            self.assertEqual(
                data["week_start"].strftime("%Y-%m-%d"),
                expected_monday,
                f"For {y}-{m:02d}-{d:02d} expected week_start {expected_monday}",
            )

    def test_public_booking_page_accepts_week_param(self):
        """Public booking page with ?week= renders and includes initial week in HTML."""
        resp = self.client.get(
            "/lessons/public-booking/tok-nav/",
            {"week": "2025-01-13"},
        )
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("2025-01-13", content)
        self.assertIn("INITIAL_WEEK_START", content)

"""
Tests for Public Booking week calendar: own vs other slot display.
"""

import json
from datetime import date, time

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.students.booking_code_service import set_booking_code
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class PublicBookingWeekOwnOtherTest(TestCase):
    """Test week API returns own/other correctly after auth."""

    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="test")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.tutor)
        self.profile.public_booking_token = "tok-abc"
        self.profile.default_working_hours = {
            "monday": [{"start": "09:00", "end": "17:00"}],
            "tuesday": [{"start": "09:00", "end": "17:00"}],
        }
        self.profile.save()

        self.student1 = Student.objects.create(
            user=self.tutor, first_name="Max", last_name="Mustermann"
        )
        self.code1 = set_booking_code(self.student1)

        self.student2 = Student.objects.create(
            user=self.tutor, first_name="Anna", last_name="Schmidt"
        )
        set_booking_code(self.student2)

        contract1 = Contract.objects.create(
            student=self.student1,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        contract2 = Contract.objects.create(
            student=self.student2,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )

        # Lesson for student1: Mon 2025-01-06 10:00
        Lesson.objects.create(
            contract=contract1,
            date=date(2025, 1, 6),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        # Lesson for student2: Mon 2025-01-06 14:00
        Lesson.objects.create(
            contract=contract2,
            date=date(2025, 1, 6),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        self.client = Client(enforce_csrf_checks=True)
        self.week_url = "/lessons/public-booking/tok-abc/week/"

    def _get_week(self, year=2025, month=1, day=6):
        return self.client.get(self.week_url, {"year": year, "month": month, "day": day})

    def _csrf_headers(self):
        self.client.get(reverse("lessons:public_booking_with_token", args=["tok-abc"]))
        csrf = self.client.cookies.get("csrftoken")
        return {"HTTP_X_CSRFTOKEN": csrf.value} if csrf else {}

    def _verify(self, name, code):
        resp = self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps({"name": name, "code": code, "tutor_token": "tok-abc"}),
            content_type="application/json",
            **self._csrf_headers(),
        )
        return resp

    def test_without_auth_no_own_labels(self):
        """Without auth, busy_intervals have no own/names."""
        resp = self._get_week()
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        week = data["week_data"]
        monday = next(d for d in week["days"] if d["date"] == "2025-01-06")
        intervals = monday.get("busy_intervals", [])
        for bi in intervals:
            self.assertFalse(bi.get("own", False))
            self.assertNotIn("label", bi)

    def test_after_auth_own_has_label(self):
        """After verify, own lessons have label."""
        resp_verify = self._verify("Max Mustermann", self.code1)
        self.assertEqual(resp_verify.status_code, 200)

        resp = self._get_week()
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        monday = next(d for d in data["week_data"]["days"] if d["date"] == "2025-01-06")
        intervals = monday.get("busy_intervals", [])
        own = [bi for bi in intervals if bi.get("own")]
        self.assertGreater(len(own), 0)
        self.assertIn("Max Mustermann", [bi.get("label") for bi in own if bi.get("label")])

    def test_other_has_no_name(self):
        """Other (Anna's lesson) must not contain Anna's name when viewing as Max."""
        self._verify("Max Mustermann", self.code1)

        resp = self._get_week()
        data = json.loads(resp.content)
        monday = next(d for d in data["week_data"]["days"] if d["date"] == "2025-01-06")
        for bi in monday.get("busy_intervals", []):
            if not bi.get("own"):
                self.assertNotIn("Anna", str(bi))
                self.assertNotIn("Schmidt", str(bi))

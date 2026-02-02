"""
Tests for booking with contract unit_duration_minutes.
"""

import json
from datetime import date, timedelta

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.booking_service import BookingService
from apps.students.booking_code_service import set_booking_code
from apps.students.models import Student
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class BookingUnitDurationTest(TestCase):
    """Test that booking validates duration against contract."""

    def setUp(self):
        cache.clear()
        self.tutor = User.objects.create_user(username="tutor", password="test")
        UserProfile.objects.get_or_create(
            user=self.tutor,
            defaults={
                "public_booking_token": "tok-x",
                "default_working_hours": {
                    "monday": [{"start": "09:00", "end": "17:00"}],
                },
            },
        )
        prof = UserProfile.objects.get(user=self.tutor)
        prof.public_booking_token = "tok-x"
        prof.default_working_hours = {"monday": [{"start": "09:00", "end": "17:00"}]}
        prof.save()

        self.student = Student.objects.create(user=self.tutor, first_name="Max", last_name="Test")
        self.booking_code = set_booking_code(self.student)

        self.contract_45 = Contract.objects.create(
            student=self.student,
            hourly_rate=30,
            unit_duration_minutes=45,
            start_date=date(2025, 1, 1),
            is_active=True,
            working_hours={"monday": [{"start": "09:00", "end": "17:00"}]},
        )
        self.contract_60 = Contract.objects.create(
            student=self.student,
            hourly_rate=35,
            unit_duration_minutes=60,
            start_date=date(2025, 2, 1),
            is_active=True,
        )

        self.client = Client()

    def _verify(self):
        resp = self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps(
                {"name": "Max Test", "code": self.booking_code, "tutor_token": "tok-x"}
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_duration_must_match_contract(self):
        """Duration must equal active contract unit_duration."""
        self._verify()
        self.contract_60.is_active = False
        self.contract_60.save()

        future = timezone.now().date() + timedelta(days=7)
        while future.weekday() != 0:
            future += timedelta(days=1)

        payload = {
            "student_id": self.student.id,
            "booking_code": self.booking_code,
            "tutor_token": "tok-x",
            "date": future.strftime("%Y-%m-%d"),
            "start_time": "10:00",
            "end_time": "10:45",
            "subject": "",
            "notes": "",
            "institute": "",
        }
        resp = self.client.post(
            reverse("lessons:public_booking_book_lesson"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        payload["start_time"] = "14:00"
        payload["end_time"] = "15:00"
        resp2 = self.client.post(
            reverse("lessons:public_booking_book_lesson"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp2.status_code, 400)
        data = json.loads(resp2.content)
        self.assertIn("duration", data.get("message", "").lower())

    def test_available_slots_use_unit_duration(self):
        """Available slots span unit_duration."""
        wh = {"monday": [{"start": "09:00", "end": "17:00"}]}
        week = BookingService.get_week_booking_data(self.contract_45.id, 2025, 1, 6, wh)
        self.assertEqual(week.get("unit_duration_minutes"), 45)
        for day_data in week["days"]:
            for slot in day_data.get("available_slots", []):
                start_min = slot[0].hour * 60 + slot[0].minute
                end_min = slot[1].hour * 60 + slot[1].minute
                self.assertEqual(end_min - start_min, 45)

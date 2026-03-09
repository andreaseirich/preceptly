"""
Tests for time-dependent travel policy (Vor-Ort: ÖPNV buffer + no-go windows).
- Vor-Ort with policy: slots in no-go/buffer are not offered; book_lesson rejects them.
- Online or no policy: slots unaffected.
"""

import json
from datetime import date, time, timedelta

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.booking_service import BookingService
from apps.lessons.travel_policy import (
    get_synthetic_occupied_for_date,
    is_slot_allowed_by_policy,
)
from apps.students.booking_code_service import set_booking_code
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone


def _next_monday() -> date:
    """Return the next Monday (or the one after if today is Monday) so the date is in the future."""
    today = timezone.now().date()
    # weekday(): 0=Monday, 6=Sunday
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


class TravelPolicySyntheticOccupiedTest(TestCase):
    """get_synthetic_occupied_for_date returns correct blocks for no-go and buffer."""

    def test_no_go_window_blocks_time(self):
        policy = {
            "enabled": True,
            "buffer_rules": [],
            "no_go_windows": [{"weekday": 0, "start_time": "14:00", "end_time": "16:00"}],
        }
        monday = date(2025, 1, 6)
        blocks = get_synthetic_occupied_for_date(monday, policy)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], time(14, 0))
        self.assertEqual(blocks[0][1], time(16, 0))

    def test_buffer_rule_blocks_before_window(self):
        policy = {
            "enabled": True,
            "buffer_rules": [
                {
                    "weekday": 0,
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "buffer_minutes": 70,
                }
            ],
            "no_go_windows": [],
        }
        monday = date(2025, 1, 6)
        blocks = get_synthetic_occupied_for_date(monday, policy)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], time(7, 50))
        self.assertEqual(blocks[0][1], time(12, 0))

    def test_disabled_policy_returns_empty(self):
        policy = {"enabled": False, "buffer_rules": [], "no_go_windows": []}
        blocks = get_synthetic_occupied_for_date(date(2025, 1, 6), policy)
        self.assertEqual(blocks, [])

    def test_is_slot_allowed_false_in_no_go(self):
        policy = {
            "enabled": True,
            "no_go_windows": [{"weekday": 0, "start_time": "14:00", "end_time": "16:00"}],
        }
        monday = date(2025, 1, 6)
        self.assertFalse(is_slot_allowed_by_policy(monday, time(14, 30), time(15, 30), policy))
        self.assertTrue(is_slot_allowed_by_policy(monday, time(10, 0), time(11, 0), policy))

    def test_fahrrad_blocks_start_of_working_segment(self):
        """Fahrrad mode: first N minutes of each working block are synthetic occupied."""
        policy = {
            "enabled": True,
            "transport_mode": "fahrrad",
            "fahrrad_buffer_minutes": 25,
        }
        working_hours = [(time(8, 0), time(12, 0))]
        blocks = get_synthetic_occupied_for_date(
            date(2025, 1, 6), policy, working_hours_for_date=working_hours
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], time(8, 0))
        self.assertEqual(blocks[0][1], time(8, 25))

    def test_fahrrad_with_dict_working_hours(self):
        """Fahrrad accepts working_hours as list of {start, end} dicts."""
        policy = {
            "enabled": True,
            "transport_mode": "fahrrad",
            "fahrrad_buffer_minutes": 30,
        }
        working_hours = [{"start": "09:00", "end": "17:00"}]
        blocks = get_synthetic_occupied_for_date(
            date(2025, 1, 6), policy, working_hours_for_date=working_hours
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], time(9, 0))
        self.assertEqual(blocks[0][1], time(9, 30))

    def test_slot_allowed_fahrrad_with_working_hours(self):
        """Slot in first buffer minutes is disallowed; after buffer is allowed."""
        policy = {
            "enabled": True,
            "transport_mode": "fahrrad",
            "fahrrad_buffer_minutes": 25,
        }
        working_hours = [{"start": "08:00", "end": "12:00"}]
        monday = date(2025, 1, 6)
        self.assertFalse(
            is_slot_allowed_by_policy(
                monday,
                time(8, 0),
                time(9, 0),
                policy,
                working_hours_for_date=working_hours,
            )
        )
        self.assertTrue(
            is_slot_allowed_by_policy(
                monday,
                time(8, 30),
                time(9, 30),
                policy,
                working_hours_for_date=working_hours,
            )
        )


class TravelPolicyBookingServiceTest(TestCase):
    """Vor-Ort with policy reduces available slots; online unchanged."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.default_working_hours = {
            "monday": [{"start": "08:00", "end": "18:00"}],
        }
        self.profile.save()
        self.student = Student.objects.create(
            user=self.user,
            first_name="S",
            last_name="T",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )

    def test_online_no_policy_has_more_slots(self):
        monday = _next_monday()
        self.profile.default_booking_location = "online"
        self.profile.travel_policy = {}
        self.profile.save()
        week_data = BookingService.get_public_booking_data(
            monday.year, monday.month, monday.day, user=self.user
        )
        monday_data = next(d for d in week_data["days"] if d["date"].weekday() == 0)
        slots_online = len(monday_data["available_slots"])

        self.profile.default_booking_location = "vor_ort"
        self.profile.travel_policy = {
            "enabled": True,
            "no_go_windows": [{"weekday": 0, "start_time": "09:00", "end_time": "17:00"}],
            "buffer_rules": [],
        }
        self.profile.save()
        week_data2 = BookingService.get_public_booking_data(
            monday.year, monday.month, monday.day, user=self.user
        )
        monday_data2 = next(d for d in week_data2["days"] if d["date"].weekday() == 0)
        slots_vor_ort = len(monday_data2["available_slots"])

        self.assertGreater(slots_online, slots_vor_ort)
        self.assertLess(
            slots_vor_ort, slots_online, "Vor-Ort with no-go should offer fewer slots than online"
        )

    def test_fahrrad_mode_more_slots_than_oepnv_no_go(self):
        """Same day: ÖPNV with no-go blocks most slots; Fahrrad with buffer gives more."""
        monday = _next_monday()
        self.profile.default_booking_location = "vor_ort"
        self.profile.travel_policy = {
            "enabled": True,
            "transport_mode": "oepnv",
            "no_go_windows": [{"weekday": 0, "start_time": "09:00", "end_time": "17:00"}],
            "buffer_rules": [],
        }
        self.profile.save()
        week_data_oepnv = BookingService.get_public_booking_data(
            monday.year, monday.month, monday.day, user=self.user
        )
        monday_oepnv = next(d for d in week_data_oepnv["days"] if d["date"].weekday() == 0)
        slots_oepnv = len(monday_oepnv["available_slots"])

        self.profile.travel_policy = {
            "enabled": True,
            "transport_mode": "fahrrad",
            "fahrrad_buffer_minutes": 25,
        }
        self.profile.save()
        week_data_fahrrad = BookingService.get_public_booking_data(
            monday.year, monday.month, monday.day, user=self.user
        )
        monday_fahrrad = next(d for d in week_data_fahrrad["days"] if d["date"].weekday() == 0)
        slots_fahrrad = len(monday_fahrrad["available_slots"])

        self.assertGreater(slots_fahrrad, slots_oepnv)


class TravelPolicyBookLessonAPITest(TestCase):
    """Booking a slot inside a no-go window returns 400 with message and alternative_slots."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.tutor = User.objects.create_user(username="tutor_tp", password="test")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.tutor)
        self.profile.public_booking_token = "tok-tp"
        self.profile.default_booking_location = "vor_ort"
        self.profile.default_working_hours = {
            "monday": [{"start": "08:00", "end": "18:00"}],
        }
        self.profile.travel_policy = {
            "enabled": True,
            "buffer_rules": [],
            "no_go_windows": [
                {"weekday": 0, "start_time": "14:00", "end_time": "16:00"},
            ],
        }
        self.profile.save()
        self.student = Student.objects.create(
            user=self.tutor,
            first_name="S",
            last_name="T",
        )
        self.booking_code = set_booking_code(self.student)
        Contract.objects.create(
            student=self.student,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )

    def _csrf_headers(self):
        self.client.get(
            reverse("lessons:public_booking_with_token", args=[self.profile.public_booking_token])
        )
        csrf = self.client.cookies.get("csrftoken")
        return {"HTTP_X_CSRFTOKEN": csrf.value} if csrf else {}

    def test_book_slot_in_no_go_returns_400_with_alternatives(self):
        """Requesting a slot inside no-go returns 400 and alternative_slots."""
        monday = _next_monday()
        r = self.client.post(
            reverse("lessons:public_booking_book_lesson"),
            data=json.dumps(
                {
                    "student_id": self.student.pk,
                    "booking_code": self.booking_code,
                    "tutor_token": "tok-tp",
                    "date": monday.isoformat(),
                    "start_time": "14:30",
                    "end_time": "15:30",
                }
            ),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(r.status_code, 400)
        data = json.loads(r.content)
        self.assertFalse(data.get("success"))
        self.assertIn("travel", data.get("message", "").lower())
        self.assertIn("alternative_slots", data)
        self.assertIsInstance(data["alternative_slots"], list)

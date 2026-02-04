"""
Public booking tutor_token isolation tests.
Week API and booking data must never contain other tutors' data.
Verify/book/reschedule must fail when tutor_token does not match session or resource.
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


class PublicBookingTutorTokenIsolationTest(TestCase):
    """tutor_token isolation: Week API and booking data must only contain that tutor's data."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.tutor_a = User.objects.create_user(username="tutor_a", password="test")
        self.tutor_b = User.objects.create_user(username="tutor_b", password="test")

        prof_a, _ = UserProfile.objects.get_or_create(user=self.tutor_a)
        prof_a.public_booking_token = "tok-a"
        prof_a.default_working_hours = {
            "monday": [{"start": "09:00", "end": "17:00"}],
        }
        prof_a.save()

        prof_b, _ = UserProfile.objects.get_or_create(user=self.tutor_b)
        prof_b.public_booking_token = "tok-b"
        prof_b.default_working_hours = {
            "monday": [{"start": "09:00", "end": "17:00"}],
        }
        prof_b.save()

        self.student_a = Student.objects.create(
            user=self.tutor_a,
            first_name="Alice",
            last_name="AStudent",
        )
        self.code_a = set_booking_code(self.student_a)

        self.student_b = Student.objects.create(
            user=self.tutor_b,
            first_name="Bob",
            last_name="BStudent",
        )
        self.code_b = set_booking_code(self.student_b)

        self.contract_a = Contract.objects.create(
            student=self.student_a,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_b = Contract.objects.create(
            student=self.student_b,
            hourly_rate=25,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

        self.lesson_a = Lesson.objects.create(
            contract=self.contract_a,
            date=date(2025, 1, 6),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        self.lesson_b = Lesson.objects.create(
            contract=self.contract_b,
            date=date(2025, 1, 6),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

    def _csrf_headers(self, token):
        self.client.get(reverse("lessons:public_booking_with_token", args=[token]))
        csrf = self.client.cookies.get("csrftoken")
        return {"HTTP_X_CSRFTOKEN": csrf.value} if csrf else {}

    def test_week_api_tok_a_returns_only_tutor_a_data(self):
        """Week API with tok-a must not contain tutor B's student/lesson data."""
        r = self.client.get(
            "/lessons/public-booking/tok-a/week/",
            {"year": 2025, "month": 1, "day": 6},
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data.get("success"))
        days = data.get("week_data", {}).get("days", [])
        monday = next((d for d in days if d["date"] == "2025-01-06"), None)
        self.assertIsNotNone(monday)
        intervals = monday.get("busy_intervals", [])
        labels = [bi.get("label", "") for bi in intervals if bi.get("label")]
        self.assertNotIn("Bob", " ".join(labels))
        self.assertNotIn("BStudent", " ".join(labels))

    def test_week_api_tok_b_returns_only_tutor_b_data(self):
        """Week API with tok-b must not contain tutor A's student/lesson data."""
        r = self.client.get(
            "/lessons/public-booking/tok-b/week/",
            {"year": 2025, "month": 1, "day": 6},
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data.get("success"))
        days = data.get("week_data", {}).get("days", [])
        monday = next((d for d in days if d["date"] == "2025-01-06"), None)
        self.assertIsNotNone(monday)
        intervals = monday.get("busy_intervals", [])
        labels = [bi.get("label", "") for bi in intervals if bi.get("label")]
        self.assertNotIn("Alice", " ".join(labels))
        self.assertNotIn("AStudent", " ".join(labels))

    def test_verify_tok_a_accepts_a_student_rejects_b_student_code(self):
        """Verify with tok-a: A's student+code works; B's student+code must fail."""
        r_ok = self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps(
                {
                    "name": "Alice AStudent",
                    "code": self.code_a,
                    "tutor_token": "tok-a",
                }
            ),
            content_type="application/json",
            **self._csrf_headers("tok-a"),
        )
        self.assertEqual(r_ok.status_code, 200)
        data_ok = json.loads(r_ok.content)
        self.assertTrue(data_ok.get("success"))

        r_fail = self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps(
                {
                    "name": "Bob BStudent",
                    "code": self.code_b,
                    "tutor_token": "tok-a",
                }
            ),
            content_type="application/json",
            **self._csrf_headers("tok-a"),
        )
        self.assertEqual(r_fail.status_code, 400)
        data_fail = json.loads(r_fail.content)
        self.assertFalse(data_fail.get("success"))

    def test_verify_tok_b_accepts_b_student_rejects_a_student_code(self):
        """Verify with tok-b: B's student+code works; A's student+code must fail."""
        r_ok = self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps(
                {
                    "name": "Bob BStudent",
                    "code": self.code_b,
                    "tutor_token": "tok-b",
                }
            ),
            content_type="application/json",
            **self._csrf_headers("tok-b"),
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertTrue(json.loads(r_ok.content).get("success"))

        r_fail = self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps(
                {
                    "name": "Alice AStudent",
                    "code": self.code_a,
                    "tutor_token": "tok-b",
                }
            ),
            content_type="application/json",
            **self._csrf_headers("tok-b"),
        )
        self.assertEqual(r_fail.status_code, 400)
        self.assertFalse(json.loads(r_fail.content).get("success"))

    def test_book_with_wrong_tutor_token_fails(self):
        """Book API with tutor_token B but student_id of A must fail (404 or 400)."""
        r = self.client.post(
            reverse("lessons:public_booking_book_lesson"),
            data=json.dumps(
                {
                    "student_id": self.student_a.pk,
                    "booking_code": self.code_a,
                    "tutor_token": "tok-b",
                    "date": "2025-01-13",
                    "start_time": "10:00",
                    "end_time": "11:00",
                }
            ),
            content_type="application/json",
            **self._csrf_headers("tok-b"),
        )
        self.assertIn(r.status_code, (400, 404))
        self.assertFalse(json.loads(r.content).get("success"))

    def test_reschedule_with_wrong_tutor_token_fails(self):
        """Reschedule with tutor_token B and lesson of A must fail (404)."""
        self.client.get(reverse("lessons:public_booking_with_token", args=["tok-b"]))
        self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps(
                {
                    "name": "Bob BStudent",
                    "code": self.code_b,
                    "tutor_token": "tok-b",
                }
            ),
            content_type="application/json",
            **self._csrf_headers("tok-b"),
        )
        r = self.client.post(
            reverse("lessons:public_booking_reschedule_lesson"),
            data=json.dumps(
                {
                    "lesson_id": self.lesson_a.pk,
                    "tutor_token": "tok-b",
                    "booking_code": self.code_b,
                    "new_date": "2025-01-13",
                    "new_start_time": "10:00",
                }
            ),
            content_type="application/json",
            **self._csrf_headers("tok-b"),
        )
        self.assertIn(r.status_code, (400, 401, 403, 404))
        self.assertFalse(json.loads(r.content).get("success"))
        self.assertTrue(Lesson.objects.filter(pk=self.lesson_a.pk).exists())

    def test_search_student_tok_a_does_not_return_tutor_b_students(self):
        """Search with tok-a must not return tutor B's students."""
        r = self.client.post(
            reverse("lessons:public_booking_search_student"),
            data=json.dumps({"name": "Bob", "tutor_token": "tok-a"}),
            content_type="application/json",
            **self._csrf_headers("tok-a"),
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        if data.get("result") == "suggestions":
            ids = [s["id"] for s in data.get("suggestions", [])]
            self.assertNotIn(self.student_b.pk, ids)
        if data.get("result") == "exact_match":
            self.assertNotEqual(data.get("student", {}).get("id"), self.student_b.pk)

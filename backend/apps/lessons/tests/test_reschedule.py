"""
Tests for Public Booking reschedule (Umbuchung) functionality.
"""

import json
from datetime import date, timedelta

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.students.booking_code_service import set_booking_code
from apps.students.models import Student
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class RescheduleTestMixin:
    def setUp(self):
        cache.clear()
        self.tutor = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=self.tutor, defaults={})
        prof.public_booking_token = "tok-reschedule"
        prof.default_working_hours = {"monday": [{"start": "09:00", "end": "17:00"}]}
        prof.save()

        self.student = Student.objects.create(
            user=self.tutor, first_name="Reschedule", last_name="Test"
        )
        self.booking_code = set_booking_code(self.student)

        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
            working_hours={"monday": [{"start": "09:00", "end": "17:00"}]},
        )

        self.client = Client(enforce_csrf_checks=True)

    def _csrf_headers(self):
        self.client.get(reverse("lessons:public_booking_with_token", args=["tok-reschedule"]))
        csrf = self.client.cookies.get("csrftoken")
        return {"HTTP_X_CSRFTOKEN": csrf.value} if csrf else {}

    def _verify(self):
        resp = self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps(
                {
                    "name": "Reschedule Test",
                    "code": self.booking_code,
                    "tutor_token": "tok-reschedule",
                }
            ),
            content_type="application/json",
            **self._csrf_headers(),
        )
        assert resp.status_code == 200, resp.content

    def _future_monday(self):
        d = timezone.now().date() + timedelta(days=7)
        while d.weekday() != 0:
            d += timedelta(days=1)
        return d


class WeekApiReschedulableTest(RescheduleTestMixin, TestCase):
    """Week API returns lesson_id and reschedulable for own planned lessons."""

    def test_busy_intervals_include_reschedulable_for_own(self):
        from datetime import time

        self._verify()
        future = self._future_monday()
        les = Lesson.objects.create(
            contract=self.contract,
            date=future,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        url = f"/lessons/public-booking/tok-reschedule/week/?year={future.year}&month={future.month}&day={future.day}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        week = data.get("week_data", {})
        found = False
        for day in week.get("days", []):
            for bi in day.get("busy_intervals", []):
                if bi.get("own") and bi.get("lesson_id") == les.id:
                    self.assertTrue(bi.get("reschedulable"))
                    found = True
        self.assertTrue(found)


class RescheduleLessonApiTest(RescheduleTestMixin, TestCase):
    """Reschedule API: happy path and failure cases."""

    def test_reschedule_happy_path(self):
        self._verify()
        future = self._future_monday()
        from datetime import time

        les = Lesson.objects.create(
            contract=self.contract,
            date=future,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

        new_date = future + timedelta(days=1)
        resp = self.client.post(
            reverse("lessons:public_booking_reschedule_lesson"),
            data=json.dumps(
                {
                    "lesson_id": les.id,
                    "new_date": new_date.strftime("%Y-%m-%d"),
                    "new_start_time": "14:00",
                    "tutor_token": "tok-reschedule",
                    "booking_code": self.booking_code,
                }
            ),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))

        les.refresh_from_db()
        self.assertEqual(les.date, new_date)
        self.assertEqual(les.start_time.hour, 14)
        self.assertEqual(les.start_time.minute, 0)

    def test_reschedule_fails_without_auth(self):
        future = self._future_monday()
        from datetime import time

        les = Lesson.objects.create(
            contract=self.contract,
            date=future,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        new_date = future + timedelta(days=1)

        resp = self.client.post(
            reverse("lessons:public_booking_reschedule_lesson"),
            data=json.dumps(
                {
                    "lesson_id": les.id,
                    "new_date": new_date.strftime("%Y-%m-%d"),
                    "new_start_time": "14:00",
                    "tutor_token": "tok-reschedule",
                    "booking_code": "wrong-code",
                }
            ),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(resp.status_code, 400)

    def test_reschedule_fails_for_other_student_lesson(self):
        other_student = Student.objects.create(
            user=self.tutor, first_name="Other", last_name="Student"
        )
        other_contract = Contract.objects.create(
            student=other_student,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )
        self._verify()

        future = self._future_monday()
        from datetime import time

        other_les = Lesson.objects.create(
            contract=other_contract,
            date=future,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

        new_date = future + timedelta(days=1)
        resp = self.client.post(
            reverse("lessons:public_booking_reschedule_lesson"),
            data=json.dumps(
                {
                    "lesson_id": other_les.id,
                    "new_date": new_date.strftime("%Y-%m-%d"),
                    "new_start_time": "14:00",
                    "tutor_token": "tok-reschedule",
                    "booking_code": self.booking_code,
                }
            ),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_reschedule_fails_for_non_planned_status(self):
        self._verify()
        future = self._future_monday()
        from datetime import time

        les = Lesson.objects.create(
            contract=self.contract,
            date=future,
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )

        new_date = future + timedelta(days=1)
        resp = self.client.post(
            reverse("lessons:public_booking_reschedule_lesson"),
            data=json.dumps(
                {
                    "lesson_id": les.id,
                    "new_date": new_date.strftime("%Y-%m-%d"),
                    "new_start_time": "14:00",
                    "tutor_token": "tok-reschedule",
                    "booking_code": self.booking_code,
                }
            ),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_reschedule_conflict_prevents(self):
        """Reschedule to occupied slot fails."""
        from datetime import time

        self._verify()
        future = self._future_monday()
        Lesson.objects.create(
            contract=self.contract,
            date=future,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        les2 = Lesson.objects.create(
            contract=self.contract,
            date=future,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )
        resp = self.client.post(
            reverse("lessons:public_booking_reschedule_lesson"),
            data=json.dumps(
                {
                    "lesson_id": les2.id,
                    "new_date": future.strftime("%Y-%m-%d"),
                    "new_start_time": "10:00",
                    "tutor_token": "tok-reschedule",
                    "booking_code": self.booking_code,
                }
            ),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(resp.status_code, 400)
        les2.refresh_from_db()
        self.assertEqual(les2.start_time.hour, 14)

    def test_reschedule_keeps_lesson_identity(self):
        """Successful reschedule updates same lesson, does not create new."""
        from datetime import time

        self._verify()
        future = self._future_monday()
        les = Lesson.objects.create(
            contract=self.contract,
            date=future,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        orig_id = les.id
        new_date = future + timedelta(days=1)
        resp = self.client.post(
            reverse("lessons:public_booking_reschedule_lesson"),
            data=json.dumps(
                {
                    "lesson_id": orig_id,
                    "new_date": new_date.strftime("%Y-%m-%d"),
                    "new_start_time": "14:00",
                    "tutor_token": "tok-reschedule",
                    "booking_code": self.booking_code,
                }
            ),
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data.get("lesson_id"), orig_id)
        self.assertEqual(Lesson.objects.filter(contract=self.contract).count(), 1)

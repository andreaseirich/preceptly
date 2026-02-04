"""
Tests for Premium gating on Public Booking (limit, reschedule).
"""

import json
from datetime import time, timedelta

from apps.contracts.models import Contract
from apps.core.feature_flags import PUBLIC_BOOKING_MONTHLY_LIMIT
from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone


class PublicBookingLimitTest(TestCase):
    """Test Basic user hits booking limit."""

    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="test")
        UserProfile.objects.create(user=self.tutor, is_premium=False)
        profile = UserProfile.objects.get(user=self.tutor)
        profile.public_booking_token = "tok-limit"
        profile.save()
        self.student = Student.objects.create(user=self.tutor, first_name="A", last_name="B")
        from apps.students.booking_code_service import set_booking_code

        self.booking_code = set_booking_code(self.student)
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=0,
            unit_duration_minutes=60,
            start_date=timezone.now().date(),
            is_active=True,
        )
        for _ in range(PUBLIC_BOOKING_MONTHLY_LIMIT):
            Lesson.objects.create(
                contract=self.contract,
                date=timezone.now().date() + timedelta(days=7),
                start_time=time(10, 0),
                duration_minutes=60,
                status="planned",
                created_via="public_booking",
            )

    def test_booking_blocked_when_limit_reached(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("lessons:public_booking_with_token", args=["tok-limit"]))
        session = client.session
        session["public_booking_tutor_token"] = "tok-limit"
        session["public_booking_student_id"] = self.student.id
        session.save()
        csrf = client.cookies.get("csrftoken")
        headers = {"HTTP_X_CSRFTOKEN": csrf.value} if csrf else {}

        future = timezone.now() + timedelta(days=14)
        dt_str = future.strftime("%Y-%m-%d")
        response = client.post(
            reverse("lessons:public_booking_book_lesson"),
            data=json.dumps(
                {
                    "student_id": self.student.id,
                    "booking_code": self.booking_code,
                    "tutor_token": "tok-limit",
                    "date": dt_str,
                    "start_time": "14:00",
                    "end_time": "15:00",
                }
            ),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("limit", response.json().get("message", "").lower())


class PublicReschedulePremiumTest(TestCase):
    """Test Basic cannot reschedule, Premium can."""

    def setUp(self):
        self.basic_tutor = User.objects.create_user(username="basic", password="test")
        UserProfile.objects.create(user=self.basic_tutor, is_premium=False)
        prof = UserProfile.objects.get(user=self.basic_tutor)
        prof.public_booking_token = "tok-basic"
        prof.save()

        self.premium_tutor = User.objects.create_user(username="premium", password="test")
        UserProfile.objects.create(user=self.premium_tutor, is_premium=True)
        prof2 = UserProfile.objects.get(user=self.premium_tutor)
        prof2.public_booking_token = "tok-prem"
        prof2.save()

        self.student = Student.objects.create(
            user=self.premium_tutor, first_name="A", last_name="B"
        )
        from apps.students.booking_code_service import set_booking_code

        set_booking_code(self.student)
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=0,
            unit_duration_minutes=60,
            start_date=timezone.now().date(),
            is_active=True,
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract,
            date=timezone.now().date() + timedelta(days=7),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        self.student_basic = Student.objects.create(
            user=self.basic_tutor, first_name="C", last_name="D"
        )
        self.booking_code_basic = set_booking_code(self.student_basic)
        self.contract_basic = Contract.objects.create(
            student=self.student_basic,
            hourly_rate=0,
            unit_duration_minutes=60,
            start_date=timezone.now().date(),
            is_active=True,
        )
        self.lesson_basic = Lesson.objects.create(
            contract=self.contract_basic,
            date=timezone.now().date() + timedelta(days=7),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

    def test_basic_reschedule_returns_403(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("lessons:public_booking_with_token", args=["tok-basic"]))
        session = client.session
        session["public_booking_tutor_token"] = "tok-basic"
        session["public_booking_student_id"] = self.student_basic.id
        session.save()
        csrf = client.cookies.get("csrftoken")
        headers = {"HTTP_X_CSRFTOKEN": csrf.value} if csrf else {}

        new_date = (timezone.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        response = client.post(
            reverse("lessons:public_booking_reschedule_lesson"),
            data=json.dumps(
                {
                    "lesson_id": self.lesson_basic.id,
                    "new_date": new_date,
                    "new_start_time": "14:00",
                    "tutor_token": "tok-basic",
                    "booking_code": self.booking_code_basic,
                }
            ),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 403)

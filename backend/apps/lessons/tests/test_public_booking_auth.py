"""
Tests for Public Booking authentication (name + code verification).
"""

import json

from apps.core.models import UserProfile
from apps.lessons.throttle import (
    THROTTLE_IP_LIMIT,
    is_public_booking_throttled,
    record_public_booking_attempt,
)
from apps.students.booking_code_service import set_booking_code, verify_booking_code
from apps.students.models import Student
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class PublicBookingAuthTest(TestCase):
    """Test Public Booking name+code authentication."""

    def setUp(self):
        cache.clear()
        self.tutor = User.objects.create_user(username="tutor", password="test")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.tutor)
        self.profile.public_booking_token = "test-token-123"
        self.profile.save()

        self.student1 = Student.objects.create(
            user=self.tutor, first_name="Max", last_name="Mustermann"
        )
        self.code1 = set_booking_code(self.student1)

        self.student2 = Student.objects.create(
            user=self.tutor, first_name="Anna", last_name="Schmidt"
        )
        self.code2 = set_booking_code(self.student2)

        self.other_tutor = User.objects.create_user(username="other", password="test")
        self.other_student = Student.objects.create(
            user=self.other_tutor, first_name="Other", last_name="Student"
        )
        set_booking_code(self.other_student)

        self.client = Client()
        self.verify_url = reverse("lessons:public_booking_verify_student")

    def _verify(self, name: str, code: str, tutor_token: str = "test-token-123"):
        return self.client.post(
            self.verify_url,
            data=json.dumps({"name": name, "code": code, "tutor_token": tutor_token}),
            content_type="application/json",
        )

    def test_name_without_code_no_access(self):
        """Name alone without code must not grant access."""
        resp = self._verify("Max Mustermann", "")
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertFalse(data.get("success"))

    def test_name_with_wrong_code_no_access(self):
        """Wrong code must not grant access (neutral message)."""
        resp = self._verify("Max Mustermann", "WRONGCODE1234")
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertFalse(data.get("success"))
        self.assertNotIn("exist", data.get("message", "").lower())

    def test_correct_code_grants_access(self):
        """Correct name+code must return only that student's data."""
        resp = self._verify("Max Mustermann", self.code1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["student"]["full_name"], "Max Mustermann")
        self.assertEqual(data["student"]["id"], self.student1.id)

    def test_correct_code_no_foreign_data(self):
        """Verify returns only the matched student, not other students."""
        resp = self._verify("Anna Schmidt", self.code2)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data["student"]["full_name"], "Anna Schmidt")
        self.assertNotIn("Max", str(data))
        self.assertNotIn("Other", str(data))

    def test_wrong_name_correct_code_no_access(self):
        """Wrong name with valid code from another student must not grant access."""
        resp = self._verify("Max Mustermann", self.code2)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(json.loads(resp.content).get("success"))

    def test_invalid_tutor_token(self):
        """Invalid tutor token must not grant access."""
        resp = self._verify("Max Mustermann", self.code1, tutor_token="invalid")
        self.assertEqual(resp.status_code, 400)

    def test_rate_limit_blocks_after_threshold(self):
        """Rate limit must block after exceeding threshold."""
        factory = RequestFactory()
        request = factory.post("/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        for _ in range(THROTTLE_IP_LIMIT):
            record_public_booking_attempt(request, "test-token-123")

        self.assertTrue(is_public_booking_throttled(request, "test-token-123"))

    def test_verify_booking_code_service(self):
        """Test verify_booking_code directly."""
        self.assertTrue(verify_booking_code(self.student1, self.code1))
        self.assertFalse(verify_booking_code(self.student1, "wrong"))
        self.assertFalse(verify_booking_code(self.student1, ""))
        self.assertFalse(verify_booking_code(self.student1, self.code2))

    def test_verify_success_cycles_session_key(self):
        """Successful verify cycles session key to reduce fixation risk."""
        self.client.get(reverse("core:landing"))
        session_key_before = self.client.session.session_key
        self.assertIsNotNone(session_key_before)
        resp = self._verify("Max Mustermann", self.code1)
        self.assertEqual(resp.status_code, 200)
        session_key_after = self.client.session.session_key
        self.assertNotEqual(session_key_before, session_key_after)

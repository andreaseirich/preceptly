"""
Tests for Public Booking step 1: name search with suggestions.
"""

import json

from apps.core.models import UserProfile
from apps.students.models import Student
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class PublicBookingSearchSuggestionsTest(TestCase):
    """Test search/suggestions API for Public Booking step 1."""

    def setUp(self):
        cache.clear()
        self.tutor_a = User.objects.create_user(username="tutor_a", password="test")
        UserProfile.objects.get_or_create(
            user=self.tutor_a, defaults={"public_booking_token": "tok-a"}
        )
        prof_a = UserProfile.objects.get(user=self.tutor_a)
        prof_a.public_booking_token = "tok-a"
        prof_a.save()

        self.tutor_b = User.objects.create_user(username="tutor_b", password="test")
        UserProfile.objects.get_or_create(
            user=self.tutor_b, defaults={"public_booking_token": "tok-b"}
        )
        prof_b = UserProfile.objects.get(user=self.tutor_b)
        prof_b.public_booking_token = "tok-b"
        prof_b.save()

        self.student_max = Student.objects.create(
            user=self.tutor_a, first_name="Max", last_name="Mustermann"
        )
        self.student_anna = Student.objects.create(
            user=self.tutor_a, first_name="Anna", last_name="Schmidt"
        )
        self.student_other = Student.objects.create(
            user=self.tutor_b, first_name="Max", last_name="Other"
        )

        self.client = Client()
        self.search_url = reverse("lessons:public_booking_search_student")

    def _search(self, name: str, tutor_token: str = "tok-a"):
        return self.client.post(
            self.search_url,
            data=json.dumps({"name": name, "tutor_token": tutor_token}),
            content_type="application/json",
        )

    def test_first_name_only_returns_suggestions(self):
        """Input only first name -> suggestions for tutor A, not tutor B students."""
        resp = self._search("Max")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("result"), "suggestions")
        names = [s["display_name"] for s in data.get("suggestions", [])]
        self.assertIn("Max Mustermann", names)
        self.assertNotIn("Max Other", names)

    def test_typo_returns_suggestions(self):
        """Input with typo -> suggestions in sensible order."""
        resp = self._search("Anma")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("result"), "suggestions")
        names = [s["display_name"] for s in data.get("suggestions", [])]
        self.assertIn("Anna Schmidt", names)

    def test_no_match_returns_no_match(self):
        """No matching student -> no_match result."""
        resp = self._search("XyzUnknown")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("result"), "no_match")
        self.assertEqual(data.get("suggestions"), [])

    def test_exact_match_returns_exact(self):
        """Exact full name -> exact_match."""
        resp = self._search("Max Mustermann")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("result"), "exact_match")
        self.assertEqual(data["student"]["display_name"], "Max Mustermann")
        self.assertEqual(data["student"]["id"], self.student_max.id)

    def test_suggestions_no_sensitive_data(self):
        """Suggestions contain only display_name and id."""
        resp = self._search("Max")
        data = json.loads(resp.content)
        for s in data.get("suggestions", []):
            self.assertIn("display_name", s)
            self.assertIn("id", s)
            self.assertNotIn("email", s)
            self.assertNotIn("phone", s)

    def test_tutor_scoping(self):
        """Search for tutor B returns only tutor B students."""
        resp = self._search("Max", tutor_token="tok-b")
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))
        names = [s["display_name"] for s in data.get("suggestions", [])]
        self.assertIn("Max Other", names)
        self.assertNotIn("Max Mustermann", names)

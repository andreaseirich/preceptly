"""
Tests for registration flow and premium default.
"""

from apps.core.models import UserProfile
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class RegisterViewTest(TestCase):
    """Tests for registration."""

    def setUp(self):
        self.client = Client()

    def test_register_creates_user_and_profile(self):
        """Registration creates User and UserProfile with is_premium=False."""
        response = self.client.post(
            reverse("core:register"),
            {
                "username": "newtutor",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="newtutor")
        self.assertTrue(user.check_password("SecurePass123!"))
        profile = UserProfile.objects.get(user=user)
        self.assertFalse(profile.is_premium)

    def test_register_redirects_authenticated_user(self):
        """Authenticated user visiting /register/ is redirected to dashboard."""
        User.objects.create_user(username="existing", password="test")
        self.client.login(username="existing", password="test")
        response = self.client.get(reverse("core:register"))
        self.assertRedirects(response, reverse("core:dashboard"))

    def test_duplicate_username_generic_error(self):
        """Duplicate username shows generic error, no enumeration."""
        User.objects.create_user(username="taken", password="test")
        response = self.client.post(
            reverse("core:register"),
            {"username": "taken", "password1": "SecurePass123!", "password2": "SecurePass123!"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertTrue(
            "Registration failed" in content
            or "Please try" in content
            or "different username" in content,
            msg="Should show generic error, not 'username exists'",
        )
        self.assertEqual(User.objects.filter(username="taken").count(), 1)

    def test_login_after_register(self):
        """After registration, user is logged in and can access dashboard."""
        response = self.client.post(
            reverse("core:register"),
            {
                "username": "fresh",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)


class PremiumGuardTest(TestCase):
    """Tests that non-premium users cannot access premium features."""

    def setUp(self):
        self.client = Client()
        self.non_premium = User.objects.create_user(username="np", password="test")
        UserProfile.objects.create(user=self.non_premium, is_premium=False)

    def test_non_premium_cannot_generate_lesson_plan(self):
        """Non-premium user gets redirect + error when POSTing to generate lesson plan."""
        from datetime import date, time

        from apps.contracts.models import Contract
        from apps.lessons.models import Session
        from apps.students.models import Student

        student = Student.objects.create(user=self.non_premium, first_name="A", last_name="B")
        contract = Contract.objects.create(
            student=student,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        session = Session.objects.create(
            contract=contract,
            date=date(2025, 3, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.client.login(username="np", password="test")
        response = self.client.post(
            reverse("ai:generate_lesson_plan", kwargs={"lesson_id": session.pk}),
            data={},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "premium")

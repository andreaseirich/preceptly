"""
Tests for premium AI lesson plan feature visibility.
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.students.models import Student


class PremiumFeatureVisibilityTest(TestCase):
    """Tests for premium feature visibility in UI."""

    def setUp(self):
        self.client = Client()

        # Create premium user
        self.premium_user = User.objects.create_user(username="premium", password="password")
        UserProfile.objects.create(user=self.premium_user, is_premium=True)

        # Create non-premium user
        self.non_premium_user = User.objects.create_user(username="regular", password="password")
        UserProfile.objects.create(user=self.non_premium_user, is_premium=False)

        # Student and lesson for premium user
        self.student = Student.objects.create(
            user=self.premium_user,
            first_name="Test",
            last_name="Student",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2023, 1, 1),
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Student and lesson for non-premium user
        self.non_premium_student = Student.objects.create(
            user=self.non_premium_user,
            first_name="Regular",
            last_name="Student",
        )
        self.non_premium_contract = Contract.objects.create(
            student=self.non_premium_student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2023, 1, 1),
        )
        self.non_premium_lesson = Lesson.objects.create(
            contract=self.non_premium_contract,
            date=date(2023, 1, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

    def test_premium_user_sees_ai_button(self):
        """Test: Premium user sees AI lesson plan generation button."""
        self.client.login(username="premium", password="password")
        response = self.client.get(reverse("lessons:detail", kwargs={"pk": self.lesson.pk}))

        self.assertEqual(response.status_code, 200)
        # Check that premium button is present (not disabled)
        self.assertContains(response, "Generate AI Lesson Plan")
        self.assertNotContains(response, "only available for premium users")

    def test_non_premium_user_sees_disabled_button(self):
        """Test: Non-premium user sees disabled button with premium notice."""
        self.client.login(username="regular", password="password")
        response = self.client.get(
            reverse("lessons:detail", kwargs={"pk": self.non_premium_lesson.pk})
        )

        self.assertEqual(response.status_code, 200)
        # Check that premium notice is shown
        self.assertContains(response, "Premium")
        self.assertContains(response, "only available for premium users")

    def test_premium_badge_in_dashboard(self):
        """Test: Premium badge is shown in dashboard for premium users."""
        self.client.login(username="premium", password="password")
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Premium")

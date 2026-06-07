"""
Tests for week view click behavior (lesson plan vs edit).
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.lessons.models import Lesson


class WeekViewClickBehaviorTest(TestCase):
    """Tests for week view click behavior."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client.login(username="testuser", password="password")

        self.student = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Test",
            last_name="Student",
        )
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
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

    def test_week_view_contains_lesson_plan_link(self):
        """Test: Week view contains link to lesson detail view for lessons (lesson plan is integrated there)."""
        response = self.client.get(reverse("lessons:week") + "?year=2023&month=1&day=15")

        self.assertEqual(response.status_code, 200)
        # Lesson plan is now integrated into the lesson detail page
        lesson_detail_url = reverse("lessons:detail", kwargs={"pk": self.lesson.pk})
        self.assertContains(response, lesson_detail_url)

    def test_week_view_contains_edit_icon_for_lesson(self):
        """Test: Week view contains edit icon/link for lessons."""
        response = self.client.get(reverse("lessons:week") + "?year=2023&month=1&day=15")

        self.assertEqual(response.status_code, 200)
        # Check that edit URL is present (should be in the edit icon)
        edit_url = reverse("lessons:update", kwargs={"pk": self.lesson.pk})
        self.assertContains(response, edit_url)
        # Check for edit icon (✏️)
        self.assertContains(response, "✏️")

    def test_lesson_plan_view_loads_correctly(self):
        """Test: Lesson plan view redirects to lesson detail page (lesson plan integrated there)."""
        response = self.client.get(
            reverse("lesson_plans:lesson_plan", kwargs={"lesson_id": self.lesson.pk})
            + "?year=2023&month=1&day=15"
        )

        self.assertEqual(response.status_code, 302)
        # Redirect target should be the lesson detail page
        self.assertIn(f"/lessons/{self.lesson.pk}/", response.url)

    def test_lesson_plan_view_has_back_to_calendar_link(self):
        """Test: Lesson plan view redirects to lesson detail (back link is in detail page)."""
        response = self.client.get(
            reverse("lesson_plans:lesson_plan", kwargs={"lesson_id": self.lesson.pk})
            + "?year=2023&month=1&day=15"
        )

        self.assertEqual(response.status_code, 302)
        # Redirect preserves year/month/day params for back navigation
        self.assertIn(f"/lessons/{self.lesson.pk}/", response.url)

    def test_lesson_plan_view_has_edit_lesson_link(self):
        """Test: Lesson plan view redirects to lesson detail page (edit link is in detail page)."""
        response = self.client.get(
            reverse("lesson_plans:lesson_plan", kwargs={"lesson_id": self.lesson.pk})
            + "?year=2023&month=1&day=15"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/lessons/{self.lesson.pk}/", response.url)

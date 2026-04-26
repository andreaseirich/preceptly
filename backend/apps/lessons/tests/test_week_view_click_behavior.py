"""
Tests for week view click behavior (lesson plan vs edit).
"""

from datetime import date, time
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class WeekViewClickBehaviorTest(TestCase):
    """Tests for week view click behavior."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client.login(username="testuser", password="password")

        self.student = Student.objects.create(
            user=self.user,
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

    def test_week_view_contains_lesson_plan_link(self):
        """Test: Week view contains link to lesson plan view for lessons."""
        response = self.client.get(reverse("lessons:week") + "?year=2023&month=1&day=15")

        self.assertEqual(response.status_code, 200)
        # Check that lesson plan URL is present
        lesson_plan_url = reverse("lesson_plans:lesson_plan", kwargs={"lesson_id": self.lesson.pk})
        self.assertContains(response, lesson_plan_url)

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
        """Test: Lesson plan view loads correctly for a lesson."""
        response = self.client.get(
            reverse("lesson_plans:lesson_plan", kwargs={"lesson_id": self.lesson.pk})
            + "?year=2023&month=1&day=15"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lesson.contract.student.full_name)
        self.assertContains(response, "Lesson Plan")

    def test_lesson_plan_view_has_back_to_calendar_link(self):
        """Test: Lesson plan view has link back to week view."""
        response = self.client.get(
            reverse("lesson_plans:lesson_plan", kwargs={"lesson_id": self.lesson.pk})
            + "?year=2023&month=1&day=15"
        )

        self.assertEqual(response.status_code, 200)
        # Check for back to calendar link
        week_url = reverse("lessons:week") + "?year=2023&month=1&day=15"
        self.assertContains(response, week_url)

    def test_lesson_plan_view_has_edit_lesson_link(self):
        """Test: Lesson plan view has link to edit lesson."""
        response = self.client.get(
            reverse("lesson_plans:lesson_plan", kwargs={"lesson_id": self.lesson.pk})
            + "?year=2023&month=1&day=15"
        )

        self.assertEqual(response.status_code, 200)
        # Check for edit lesson link
        edit_url = reverse("lessons:update", kwargs={"pk": self.lesson.pk})
        self.assertContains(response, edit_url)
        self.assertContains(response, "Edit Lesson")

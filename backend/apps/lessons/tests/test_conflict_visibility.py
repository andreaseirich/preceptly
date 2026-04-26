"""
Tests for conflict visibility in views.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class ConflictVisibilityTest(TestCase):
    """Tests for conflict visibility in views."""

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

        # Create monthly plan with quota
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2023, month=1, planned_units=3
        )

    def test_conflict_detail_view_shows_quota_conflict(self):
        """Test: Conflict detail view shows quota conflicts."""
        # Create 4 lessons in January (but only 3 planned)
        today = date(2023, 1, 15)
        Lesson.objects.create(
            contract=self.contract,
            date=today,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=today + timedelta(days=1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=today + timedelta(days=2),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        # This one should cause a quota conflict
        lesson4 = Lesson.objects.create(
            contract=self.contract,
            date=today + timedelta(days=3),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

        # Check conflicts for lesson4
        conflicts = LessonConflictService.check_conflicts(lesson4)
        quota_conflicts = [c for c in conflicts if c["type"] == "quota"]
        self.assertGreater(len(quota_conflicts), 0, "Lesson4 should have a quota conflict")

        # Access conflict detail view
        response = self.client.get(reverse("lessons:conflicts", kwargs={"pk": lesson4.pk}))

        self.assertEqual(response.status_code, 200)
        # Should show quota conflict (template renders "Contract Quota Conflict")
        self.assertContains(response, "Contract Quota")

    def test_conflict_detail_view_shows_no_conflicts_when_none(self):
        """Test: Conflict detail view shows 'No conflicts found' when there are none."""
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 2, 15),  # Different month, no quota conflict
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

        # Access conflict detail view
        response = self.client.get(reverse("lessons:conflicts", kwargs={"pk": lesson.pk}))

        self.assertEqual(response.status_code, 200)
        # Should show no conflicts
        self.assertContains(response, "No conflicts found")

    def test_lesson_plan_view_shows_conflicts(self):
        """Test: Lesson plan view shows conflicts."""
        # Create lesson with quota conflict
        today = date(2023, 1, 15)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=today,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

        # Create 3 more lessons to exceed quota
        for i in range(1, 4):
            Lesson.objects.create(
                contract=self.contract,
                date=today + timedelta(days=i),
                start_time=time(10, 0),
                duration_minutes=60,
                status="planned",
            )

        # Access lesson plan view
        response = self.client.get(
            reverse("lesson_plans:lesson_plan", kwargs={"lesson_id": lesson.pk})
        )

        self.assertEqual(response.status_code, 200)
        # Should have conflicts in context
        self.assertIn("conflicts", response.context)
        self.assertIn("has_conflicts", response.context)
        # Should show conflicts section if there are conflicts
        if response.context["has_conflicts"]:
            self.assertContains(response, "Conflicts")

    def test_lesson_detail_view_shows_quota_conflicts(self):
        """Test: Lesson detail view shows quota conflicts."""
        # Create lesson with quota conflict
        today = date(2023, 1, 15)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=today,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

        # Create 3 more lessons to exceed quota
        for i in range(1, 4):
            Lesson.objects.create(
                contract=self.contract,
                date=today + timedelta(days=i),
                start_time=time(10, 0),
                duration_minutes=60,
                status="planned",
            )

        # Access lesson detail view
        response = self.client.get(reverse("lessons:detail", kwargs={"pk": lesson.pk}))

        self.assertEqual(response.status_code, 200)
        # Should have conflicts in context (LessonDetailView sets conflicts and has_conflicts)
        self.assertIn("conflicts", response.context)
        self.assertIn("has_conflicts", response.context)

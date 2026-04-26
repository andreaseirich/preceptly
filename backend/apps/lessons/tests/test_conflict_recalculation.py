"""
Tests for conflict recalculation after lesson/blocked time changes.
"""

from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService
from apps.students.models import Student


class ConflictRecalculationTest(TestCase):
    """Tests for conflict recalculation after changes."""

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

    def test_conflict_disappears_after_lesson_time_change(self):
        """Test: Conflict disappears when lesson time is changed via update view."""
        # Create two overlapping lessons
        lesson1 = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        lesson2 = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 15),
            start_time=time(14, 30),  # Overlaps with lesson1
            duration_minutes=60,
            status="planned",
        )

        # Check initial conflict
        conflicts1 = LessonConflictService.check_conflicts(lesson1)
        conflicts2 = LessonConflictService.check_conflicts(lesson2)
        self.assertGreater(len(conflicts1), 0)
        self.assertGreater(len(conflicts2), 0)

        # Move lesson2 to a different time via update view (triggers recalculation)
        response = self.client.post(
            reverse("lessons:update", kwargs={"pk": lesson2.pk}),
            {
                "contract": self.contract.pk,
                "date": "2023-01-15",
                "start_time": "16:00",  # No overlap
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)  # Redirect after update

        # Refresh from database
        lesson1.refresh_from_db()
        lesson2.refresh_from_db()

        # Conflicts should be recalculated - check only lesson conflicts (not quota)
        conflicts1_after = LessonConflictService.check_conflicts(lesson1)
        conflicts2_after = LessonConflictService.check_conflicts(lesson2)

        # Filter out quota conflicts (they might still exist)
        lesson_conflicts1 = [c for c in conflicts1_after if c["type"] == "lesson"]
        lesson_conflicts2 = [c for c in conflicts2_after if c["type"] == "lesson"]

        self.assertEqual(
            len(lesson_conflicts1), 0, f"Lesson1 still has conflicts: {conflicts1_after}"
        )
        self.assertEqual(
            len(lesson_conflicts2), 0, f"Lesson2 still has conflicts: {conflicts2_after}"
        )

    def test_conflict_disappears_after_blocked_time_deletion(self):
        """Test: Conflict disappears when blocking blocked time is deleted via delete view."""

        # Create a lesson
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Create overlapping blocked time
        blocked_time = BlockedTime.objects.create(
            user=self.user,
            title="Test Block",
            start_datetime=timezone.make_aware(datetime(2023, 1, 15, 14, 30)),
            end_datetime=timezone.make_aware(datetime(2023, 1, 15, 15, 30)),
        )

        # Check conflict exists
        conflicts = LessonConflictService.check_conflicts(lesson)
        self.assertGreater(len(conflicts), 0)

        # Delete blocked time via delete view (triggers recalculation)
        response = self.client.post(reverse("blocked_times:delete", kwargs={"pk": blocked_time.pk}))

        self.assertEqual(response.status_code, 302)  # Redirect after delete

        # Refresh lesson from database
        lesson.refresh_from_db()

        # Conflict should be gone - check only blocked_time conflicts (not quota)
        conflicts_after = LessonConflictService.check_conflicts(lesson)
        blocked_time_conflicts = [c for c in conflicts_after if c["type"] == "blocked_time"]

        self.assertEqual(
            len(blocked_time_conflicts),
            0,
            f"Lesson still has blocked_time conflicts: {conflicts_after}",
        )

    def test_quota_conflict_displayed_with_reason(self):
        """Test: Quota conflict is displayed with reason in UI."""
        from apps.contracts.models import ContractMonthlyPlan

        # Create contract with monthly plan
        contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )

        # Plan 3 units for January
        ContractMonthlyPlan.objects.create(contract=contract, year=2023, month=1, planned_units=3)

        # Create 3 lessons (should be OK)
        for i in range(3):
            Lesson.objects.create(
                contract=contract,
                date=date(2023, 1, 5 + i),
                start_time=time(14, 0),
                duration_minutes=60,
                status="planned",
            )

        # Create 4th lesson (should cause quota conflict)
        lesson4 = Lesson.objects.create(
            contract=contract,
            date=date(2023, 1, 8),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Check quota conflict
        conflicts = LessonConflictService.check_conflicts(lesson4)
        quota_conflicts = [c for c in conflicts if c["type"] == "quota"]
        self.assertGreater(len(quota_conflicts), 0)
        self.assertIn("message", quota_conflicts[0])
        self.assertIn("planned_total", quota_conflicts[0])
        self.assertIn("actual_total", quota_conflicts[0])

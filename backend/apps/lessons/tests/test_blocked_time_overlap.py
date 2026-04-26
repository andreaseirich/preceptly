"""
Tests for blocked time overlap detection edge cases.
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService
from apps.students.models import Student


class BlockedTimeOverlapTest(TestCase):
    """Tests for blocked time overlap detection."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
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

    def test_no_overlap_different_days(self):
        """Test: Lesson and blocked time on different days → NO conflict."""
        # Lesson: 17.12.2025, 16:00, 60 Min.
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 12, 17),
            start_time=time(16, 0),
            duration_minutes=60,
            status="planned",
        )

        # Blocked Time: "Urlaub" 15.12.2025 00:00 – 23:59
        BlockedTime.objects.create(
            user=self.user,
            title="Urlaub",
            description="Vacation",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 12, 15), time(0, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 12, 15), time(23, 59))
            ),
            is_recurring=False,
        )

        # Check conflicts
        conflicts = LessonConflictService.check_conflicts(lesson)
        blocked_time_conflicts = [c for c in conflicts if c["type"] == "blocked_time"]

        # Should have NO blocked time conflict
        self.assertEqual(
            len(blocked_time_conflicts),
            0,
            "Lesson on 17.12 should not conflict with blocked time on 15.12",
        )

    def test_overlap_lesson_within_blocked_time(self):
        """Test: Lesson within a multi-day blocked time → YES conflict."""
        # Blocked Time: "Urlaub" 15.12.2025 00:00 – 18.12.2025 23:59
        blocked_time = BlockedTime.objects.create(
            user=self.user,
            title="Urlaub",
            description="Multi-day vacation",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 12, 15), time(0, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 12, 18), time(23, 59))
            ),
            is_recurring=False,
        )

        # Lesson: 17.12.2025, 16:00, 60 Min. (within vacation)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 12, 17),
            start_time=time(16, 0),
            duration_minutes=60,
            status="planned",
        )

        # Check conflicts
        conflicts = LessonConflictService.check_conflicts(lesson)
        blocked_time_conflicts = [c for c in conflicts if c["type"] == "blocked_time"]

        # Should have blocked time conflict
        self.assertEqual(
            len(blocked_time_conflicts), 1, "Lesson within vacation period should conflict"
        )
        self.assertEqual(blocked_time_conflicts[0]["object"], blocked_time)

    def test_no_overlap_exact_boundary(self):
        """Test: Lesson ends exactly when blocked time starts → NO conflict (boundary case)."""
        # Blocked Time: starts at 17:00
        BlockedTime.objects.create(
            user=self.user,
            title="Meeting",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 12, 17), time(17, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 12, 17), time(18, 0))
            ),
            is_recurring=False,
        )

        # Lesson: 16:00-17:00 (ends exactly when blocked time starts)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 12, 17),
            start_time=time(16, 0),
            duration_minutes=60,
            status="planned",
        )

        # Check conflicts
        conflicts = LessonConflictService.check_conflicts(lesson)
        blocked_time_conflicts = [c for c in conflicts if c["type"] == "blocked_time"]

        # Should have NO conflict (boundary: end == start means no overlap)
        self.assertEqual(
            len(blocked_time_conflicts),
            0,
            "Lesson ending exactly when blocked time starts should not conflict",
        )

    def test_overlap_partial(self):
        """Test: Lesson partially overlaps with blocked time → YES conflict."""
        # Blocked Time: 14:00-16:00
        BlockedTime.objects.create(
            user=self.user,
            title="Meeting",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 12, 17), time(14, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 12, 17), time(16, 0))
            ),
            is_recurring=False,
        )

        # Lesson: 15:00-17:00 (overlaps with blocked time)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 12, 17),
            start_time=time(15, 0),
            duration_minutes=120,
            status="planned",
        )

        # Check conflicts
        conflicts = LessonConflictService.check_conflicts(lesson)
        blocked_time_conflicts = [c for c in conflicts if c["type"] == "blocked_time"]

        # Should have conflict
        self.assertEqual(
            len(blocked_time_conflicts),
            1,
            "Lesson partially overlapping with blocked time should conflict",
        )

    def test_intervals_overlap_helper_function(self):
        """Test: intervals_overlap helper function works correctly."""
        dt1 = timezone.make_aware(timezone.datetime(2025, 12, 17, 16, 0))
        dt2 = timezone.make_aware(timezone.datetime(2025, 12, 17, 17, 0))
        dt3 = timezone.make_aware(timezone.datetime(2025, 12, 17, 17, 0))
        dt4 = timezone.make_aware(timezone.datetime(2025, 12, 17, 18, 0))
        dt5 = timezone.make_aware(timezone.datetime(2025, 12, 17, 15, 0))
        dt6 = timezone.make_aware(timezone.datetime(2025, 12, 17, 16, 0))

        # Adjacent: dt1-dt2 (16:00-17:00) is adjacent to dt5-dt6 (15:00-16:00) -> NO overlap
        self.assertFalse(LessonConflictService.intervals_overlap(dt1, dt2, dt5, dt6))

        # No overlap: dt1-dt2 does not overlap with dt3-dt4 (boundary)
        self.assertFalse(LessonConflictService.intervals_overlap(dt1, dt2, dt3, dt4))

        # Overlap: dt1-dt2 overlaps with dt5-dt4 (partial)
        self.assertTrue(LessonConflictService.intervals_overlap(dt1, dt2, dt5, dt4))

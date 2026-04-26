"""
Integration tests for lesson scheduling, conflicts, and billing workflows.
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import Invoice
from apps.billing.services import InvoiceService
from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_service import RecurringLessonService
from apps.lessons.services import LessonConflictService
from apps.students.models import Student


class RecurringLessonIntegrationTest(TestCase):
    """Integration tests for recurring lesson generation."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.student = Student.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2023, 1, 1),
        )

    def test_recurring_lesson_generation_weekly(self):
        """Test that weekly recurring lessons are generated correctly."""
        # Create recurring lesson: every Monday at 14:00
        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=date(2023, 1, 2),  # Monday
            end_date=date(2023, 1, 30),
            start_time=time(14, 0),
            duration_minutes=60,
            recurrence_type="weekly",
            monday=True,
            is_active=True,
        )

        # Generate lessons
        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        # Should generate 5 lessons (5 Mondays in January 2023: Jan 2,9,16,23,30)
        self.assertEqual(result["created"], 5)
        self.assertEqual(result["skipped"], 0)

        # Verify lessons were created
        lessons = Lesson.objects.filter(contract=self.contract)
        self.assertEqual(lessons.count(), 5)

        # Verify all lessons are on Mondays
        for lesson in lessons:
            self.assertEqual(lesson.date.weekday(), 0)  # Monday = 0
            self.assertEqual(lesson.start_time, time(14, 0))
            self.assertEqual(lesson.duration_minutes, 60)

    def test_recurring_lesson_skips_existing(self):
        """Test that recurring lesson generation skips existing lessons."""
        # Create a lesson manually
        Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 2),  # Monday
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Create recurring lesson for same time
        recurring = RecurringLesson.objects.create(
            contract=self.contract,
            start_date=date(2023, 1, 2),
            end_date=date(2023, 1, 30),
            start_time=time(14, 0),
            duration_minutes=60,
            recurrence_type="weekly",
            monday=True,
            is_active=True,
        )

        # Generate lessons
        result = RecurringLessonService.generate_lessons(recurring, check_conflicts=False)

        # Should skip the existing lesson
        self.assertEqual(result["skipped"], 1)
        # Should create 4 new lessons (5 Mondays - 1 existing)
        self.assertEqual(result["created"], 4)


class ConflictDetectionIntegrationTest(TestCase):
    """Integration tests for conflict detection."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Set up test data."""
        self.student = Student.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2023, 1, 1),
        )

    def test_lesson_conflict_with_other_lesson(self):
        """Test that overlapping lessons are detected as conflicts."""
        # Create first lesson: 14:00-15:00
        lesson1 = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 2),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Create overlapping lesson: 14:30-15:30
        lesson2 = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 2),
            start_time=time(14, 30),
            duration_minutes=60,
            status="planned",
        )

        # Check conflicts
        conflicts = LessonConflictService.check_conflicts(lesson2)

        # Should detect conflict with lesson1
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "lesson")
        self.assertEqual(conflicts[0]["object"], lesson1)

    def test_lesson_conflict_with_blocked_time(self):
        """Test that lessons overlapping with blocked times are detected."""
        # Create blocked time: 14:00-15:00
        blocked_time = BlockedTime.objects.create(
            user=self.user,
            title="University Lecture",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2023, 1, 2), time(14, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2023, 1, 2), time(15, 0))
            ),
        )

        # Create overlapping lesson: 14:30-15:30
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 2),
            start_time=time(14, 30),
            duration_minutes=60,
            status="planned",
        )

        # Check conflicts
        conflicts = LessonConflictService.check_conflicts(lesson)

        # Should detect conflict with blocked time
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "blocked_time")
        self.assertEqual(conflicts[0]["object"], blocked_time)


class BillingIntegrationTest(TestCase):
    """Integration tests for billing workflow."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client = Client()
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

    def test_invoice_creation_marks_lessons_as_paid(self):
        """Test that creating an invoice marks lessons as paid."""
        # Create taught lessons
        lesson1 = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        lesson2 = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 12),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Create invoice
        invoice = InvoiceService.create_invoice_from_lessons(
            period_start=date(2023, 1, 1), period_end=date(2023, 1, 31), contract=self.contract
        )

        # Verify invoice was created
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.items.count(), 2)

        # Verify lessons are marked as paid
        lesson1.refresh_from_db()
        lesson2.refresh_from_db()
        self.assertEqual(lesson1.status, "paid")
        self.assertEqual(lesson2.status, "paid")

        # Verify invoice items
        items = invoice.items.all()
        self.assertEqual(items[0].lesson, lesson1)
        self.assertEqual(items[1].lesson, lesson2)

    def test_invoice_deletion_reverts_lesson_status(self):
        """Test that deleting an invoice reverts lessons to taught status."""
        # Create taught lesson
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Create invoice (marks lesson as paid)
        invoice = InvoiceService.create_invoice_from_lessons(
            period_start=date(2023, 1, 1), period_end=date(2023, 1, 31), contract=self.contract
        )

        # Verify lesson is paid
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "paid")

        # Delete invoice
        InvoiceService.delete_invoice(invoice)

        # Verify lesson is reverted to taught
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")

        # Verify invoice is deleted
        self.assertFalse(Invoice.objects.filter(pk=invoice.pk).exists())


class WeeklyCalendarIntegrationTest(TestCase):
    """Integration tests for weekly calendar view."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.student = Student.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2023, 1, 1),
        )

    def test_week_view_loads_correctly(self):
        """Test that week view loads with correct data."""
        # Create a lesson in a specific week
        Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 1, 4),  # Wednesday
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Access week view
        response = self.client.get(reverse("lessons:week"), {"year": 2023, "month": 1, "day": 4})

        self.assertEqual(response.status_code, 200)
        # Verify lesson appears in response
        self.assertIn(self.student.first_name.encode(), response.content)

    def test_week_view_redirect_after_create(self):
        """Test that after creating a lesson, user stays in the same week."""
        # Create lesson via form
        response = self.client.post(
            reverse("lessons:create"),
            {
                "contract": self.contract.pk,
                "date": "2023-01-04",
                "start_time": "14:00",
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
            },
            follow=True,
        )

        # Should redirect back to week view or calendar
        self.assertEqual(response.status_code, 200)
        # Verify lesson was created
        self.assertTrue(
            Lesson.objects.filter(contract=self.contract, date=date(2023, 1, 4)).exists()
        )

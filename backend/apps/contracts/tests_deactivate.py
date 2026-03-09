"""
Tests for contract deactivation behavior.
"""

from datetime import date, timedelta
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase


class ContractDeactivateDeletesFutureLessonsTest(TestCase):
    """When contract is set to inactive, future lessons are deleted."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tutor", email="tutor@test.com", password="test123"
        )
        self.student = Student.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            email="test@example.com",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date.today() - timedelta(days=30),
            end_date=None,
            is_active=True,
        )

    def test_deactivate_deletes_future_lessons(self):
        """Setting is_active=False deletes all future lessons."""
        today = date.today()
        past_date = today - timedelta(days=5)
        future_date = today + timedelta(days=7)

        Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time="10:00",
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=future_date,
            start_time="10:00",
            duration_minutes=60,
            status="planned",
        )

        self.assertEqual(Lesson.objects.filter(contract=self.contract).count(), 2)

        self.contract.is_active = False
        self.contract.save()

        remaining = Lesson.objects.filter(contract=self.contract)
        self.assertEqual(remaining.count(), 1)
        self.assertEqual(remaining.first().date, past_date)

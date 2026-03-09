"""
Tests for contract monthly planning summary with carry-over logic.
"""

from datetime import date
from decimal import Decimal

from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.contracts.services import (
    get_contract_monthly_planning_summary,
)
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase


class ContractMonthlySummaryCarryOverTest(TestCase):
    """Tests for carry-over of remaining units to next month."""

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
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
            is_active=True,
            has_monthly_planning_limit=True,
        )
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=1, planned_units=8
        )
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=2, planned_units=6
        )
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=3, planned_units=6
        )

    def test_carry_over_remaining_to_next_month(self):
        """January: 8 planned, 5 taught => 3 remaining. February gets +3 carried over."""
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 10),
            start_time="10:00",
            duration_minutes=60,
            status="taught",
        )
        for _ in range(4):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2025, 1, 15),
                start_time="10:00",
                duration_minutes=60,
                status="taught",
            )

        summary = get_contract_monthly_planning_summary(self.contract, year=2025)
        self.assertEqual(len(summary), 3)

        jan = summary[0]
        self.assertEqual(jan["planned_units"], 8)
        self.assertEqual(jan["carried_over_units"], 0)
        self.assertEqual(jan["taught_units"], 5)
        self.assertEqual(jan["remaining_units"], 3)

        feb = summary[1]
        self.assertEqual(feb["planned_units"], 6)
        self.assertEqual(feb["carried_over_units"], 3)
        self.assertEqual(feb["taught_units"], 0)
        self.assertEqual(feb["remaining_units"], 9)

        mar = summary[2]
        self.assertEqual(mar["planned_units"], 6)
        self.assertEqual(mar["carried_over_units"], 9)
        self.assertEqual(mar["taught_units"], 0)
        self.assertEqual(mar["remaining_units"], 15)

    def test_scheduled_lessons_not_counted_as_missing(self):
        """Lessons in calendar (status=planned) reduce remaining, not counted as missing."""
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 10),
            start_time="10:00",
            duration_minutes=60,
            status="taught",
        )
        for _ in range(2):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2025, 1, 15),
                start_time="10:00",
                duration_minutes=60,
                status="taught",
            )
        for _ in range(3):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2025, 1, 20),
                start_time="10:00",
                duration_minutes=60,
                status="planned",
            )

        summary = get_contract_monthly_planning_summary(self.contract, year=2025)
        jan = summary[0]
        self.assertEqual(jan["planned_units"], 8)
        self.assertEqual(jan["taught_units"], 3)
        self.assertEqual(jan["scheduled_units"], 3)
        self.assertEqual(jan["remaining_units"], 2)

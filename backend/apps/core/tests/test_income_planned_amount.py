from datetime import date, time
from decimal import Decimal

from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.core.selectors import IncomeSelector
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.test import TestCase
from django.contrib.auth.models import User


class IncomeSelectorPlannedAmountTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Planned", last_name="Test", email="planned@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=45,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_planned_amount_uses_units_only(self):
        ContractMonthlyPlan.objects.create(
            contract=self.contract,
            year=2025,
            month=12,
            planned_units=2,
        )

        result = IncomeSelector.get_monthly_planned_vs_actual(2025, 12)

        self.assertEqual(result["planned_units"], 2)
        self.assertEqual(result["planned_amount"], Decimal("40.00"))

    def test_actual_amount_with_90_min_lesson_counts_two_units(self):
        ContractMonthlyPlan.objects.create(
            contract=self.contract,
            year=2025,
            month=12,
            planned_units=2,
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 12, 10),
            start_time=time(9, 0),
            duration_minutes=90,
            status="taught",
        )

        result = IncomeSelector.get_monthly_planned_vs_actual(2025, 12)

        self.assertEqual(result["actual_units"], 1)
        self.assertEqual(result["actual_amount"], Decimal("40.00"))
        self.assertEqual(result["difference_amount"], Decimal("0.00"))

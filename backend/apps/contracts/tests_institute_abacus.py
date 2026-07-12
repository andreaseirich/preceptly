"""No billing on tutor no-show, for any institute with the flag enabled."""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.models import Contract, Institute
from apps.core.selectors import IncomeSelector
from apps.lessons.models import Lesson


class NoShowUnpaidInstituteBillingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_abacus_ns", password="x")
        self.institute = Institute.objects.create(
            user=self.user, institute_name="Abacus", unpaid_on_tutor_no_show=True
        )
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            institute_fk=self.institute,
            hourly_rate=Decimal("24.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )

    def test_no_show_not_billed(self):
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=True,
        )
        self.assertEqual(IncomeSelector._calculate_lesson_amount(lesson), Decimal("0.00"))

    def test_normal_lesson_billed(self):
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=False,
        )
        self.assertEqual(IncomeSelector._calculate_lesson_amount(lesson), Decimal("24.00"))

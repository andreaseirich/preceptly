"""Abacus vs TutorSpace behavior for tutor_no_show."""

from datetime import date, time
from decimal import Decimal

from apps.contracts.institute_utils import ABACUS_INSTITUTE_NAME, is_abacus_institute
from apps.contracts.models import Contract
from apps.core.selectors import IncomeSelector
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase


class InstituteUtilsTest(TestCase):
    def test_abacus_name_case_insensitive(self):
        self.assertTrue(is_abacus_institute("Abacus"))
        self.assertTrue(is_abacus_institute("ABACUS"))
        self.assertTrue(is_abacus_institute(" abacus "))
        self.assertFalse(is_abacus_institute("TutorSpace"))


class AbacusTutorNoShowBillingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_abacus_ns", password="x")
        self.student = Student.objects.create(user=self.user, first_name="A", last_name="Student")
        self.contract = Contract.objects.create(
            student=self.student,
            institute=ABACUS_INSTITUTE_NAME,
            hourly_rate=Decimal("24.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )

    def test_abacus_no_show_not_billed(self):
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=True,
        )
        self.assertEqual(IncomeSelector._calculate_lesson_amount(lesson), Decimal("0.00"))

    def test_abacus_normal_lesson_billed(self):
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=False,
        )
        self.assertEqual(IncomeSelector._calculate_lesson_amount(lesson), Decimal("24.00"))

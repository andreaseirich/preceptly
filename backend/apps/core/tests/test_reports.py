"""
Tests for Reports page: Basic teaser vs Premium full, multi-user isolation.
"""

from datetime import date, time
from decimal import Decimal

from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class ReportsPremiumGatingTest(TestCase):
    """Basic sees teaser only; Premium sees full analytics."""

    def setUp(self):
        self.basic = User.objects.create_user(username="basic", password="test")
        UserProfile.objects.create(user=self.basic, is_premium=False)
        self.premium = User.objects.create_user(username="premium", password="test")
        UserProfile.objects.create(user=self.premium, is_premium=True)
        self.student_a = Student.objects.create(
            user=self.premium, first_name="A", last_name="Student"
        )
        self.contract = Contract.objects.create(
            student=self.student_a,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 10),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=self.contract, user=self.premium
        )

    def test_basic_sees_teaser_no_premium_sections(self):
        """Basic user sees teaser; no revenue_last_6, hours_last_6, breakdown_by_institute."""
        self.client.login(username="basic", password="test")
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Premium")
        self.assertContains(response, "Upgrade")
        self.assertNotContains(response, "Revenue (last 6 months)")
        self.assertNotContains(response, "Hours taught (last 6 months)")
        self.assertNotContains(response, "Revenue by institute")

    def test_premium_sees_full_sections(self):
        """Premium user sees full reports with computed sections."""
        self.client.login(username="premium", password="test")
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revenue (last 6 months)")
        self.assertContains(response, "Hours taught (last 6 months)")
        self.assertContains(response, "Top 5 students")


class ReportsMultiUserIsolationTest(TestCase):
    """User A never sees User B data."""

    def setUp(self):
        self.user_a = User.objects.create_user(username="a", password="test")
        UserProfile.objects.create(user=self.user_a, is_premium=True)
        self.user_b = User.objects.create_user(username="b", password="test")
        UserProfile.objects.create(user=self.user_b, is_premium=True)
        student_a = Student.objects.create(user=self.user_a, first_name="A", last_name="X")
        student_b = Student.objects.create(user=self.user_b, first_name="B", last_name="Y")
        contract_a = Contract.objects.create(
            student=student_a,
            hourly_rate=Decimal("25"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        contract_b = Contract.objects.create(
            student=student_b,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=contract_a,
            date=date(2025, 3, 5),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=contract_b,
            date=date(2025, 3, 6),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.inv_a = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=contract_a, user=self.user_a
        )
        self.inv_b = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=contract_b, user=self.user_b
        )

    def test_user_a_sees_only_own_student_in_reports(self):
        """User A's reports contain only A's student, not B's."""
        self.client.login(username="a", password="test")
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A X")
        self.assertNotContains(response, "B Y")

    def test_user_b_sees_only_own_student_in_reports(self):
        """User B's reports contain only B's student, not A's."""
        self.client.login(username="b", password="test")
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "B Y")
        self.assertNotContains(response, "A X")

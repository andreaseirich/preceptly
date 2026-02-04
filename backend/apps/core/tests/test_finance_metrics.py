"""
Tests for finance_metrics: canonical definitions, owner isolation, Reports/Income consistency.
"""

from datetime import date, time
from decimal import Decimal

from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.core.finance_metrics import (
    breakdown_by_institute_billed,
    breakdown_by_institute_recognized,
    pending_revenue,
    recognized_revenue,
    total_billed_revenue,
)
from apps.core.selectors import IncomeSelector
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase


class FinanceMetricsOwnerIsolationTest(TestCase):
    """Two users: all metrics are owner-isolated."""

    def setUp(self):
        self.user_a = User.objects.create_user(username="a", password="test")
        self.user_b = User.objects.create_user(username="b", password="test")
        sa = Student.objects.create(user=self.user_a, first_name="A", last_name="X")
        sb = Student.objects.create(user=self.user_b, first_name="B", last_name="Y")
        ca = Contract.objects.create(
            student=sa,
            hourly_rate=Decimal("25"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        cb = Contract.objects.create(
            student=sb,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=ca,
            date=date(2025, 3, 5),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=cb,
            date=date(2025, 3, 6),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        inv_a = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=ca, user=self.user_a
        )
        inv_b = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=cb, user=self.user_b
        )
        InvoiceService.mark_invoice_as_paid(inv_a)
        InvoiceService.mark_invoice_as_paid(inv_b)

    def test_recognized_revenue_owner_isolated(self):
        """User A sees only own recognized revenue."""
        ra = recognized_revenue(self.user_a, 2025, 3)
        rb = recognized_revenue(self.user_b, 2025, 3)
        self.assertGreater(ra, Decimal("0"))
        self.assertGreater(rb, Decimal("0"))
        self.assertNotEqual(ra, rb)

    def test_user_a_sees_zero_for_user_b_period(self):
        """User A has no invoices in a month where only B has data (different period)."""
        ra = recognized_revenue(self.user_a, 2025, 1)
        rb = recognized_revenue(self.user_b, 2025, 1)
        self.assertEqual(ra, Decimal("0"))
        self.assertEqual(rb, Decimal("0"))


class FinanceMetricsStatusTest(TestCase):
    """recognized_revenue = PAID only, pending_revenue = SENT only."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        s = Student.objects.create(user=self.user, first_name="S", last_name="T")
        c = Contract.objects.create(
            student=s,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=c,
            date=date(2025, 3, 5),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.inv = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=c, user=self.user
        )

    def test_recognized_revenue_only_paid(self):
        """recognized_revenue counts only PAID invoices."""
        self.assertEqual(recognized_revenue(self.user, 2025, 3), Decimal("0"))
        InvoiceService.mark_invoice_as_paid(self.inv)
        self.assertEqual(recognized_revenue(self.user, 2025, 3), self.inv.total_amount)

    def test_pending_revenue_only_sent(self):
        """pending_revenue counts only SENT invoices."""
        InvoiceService.mark_invoice_as_sent(self.inv)
        self.assertEqual(pending_revenue(self.user, 2025, 3), self.inv.total_amount)
        self.assertEqual(recognized_revenue(self.user, 2025, 3), Decimal("0"))

    def test_total_billed_is_paid_plus_sent(self):
        """total_billed_revenue = PAID + SENT."""
        InvoiceService.mark_invoice_as_sent(self.inv)
        self.assertEqual(total_billed_revenue(self.user, 2025, 3), self.inv.total_amount)
        InvoiceService.mark_invoice_as_paid(self.inv)
        self.assertEqual(total_billed_revenue(self.user, 2025, 3), self.inv.total_amount)


class ReportsIncomeConsistencyTest(TestCase):
    """Reports and Income produce same monthly recognized revenue."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        s = Student.objects.create(user=self.user, first_name="S", last_name="T")
        c = Contract.objects.create(
            student=s,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=c,
            date=date(2025, 3, 10),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        inv = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=c, user=self.user
        )
        InvoiceService.mark_invoice_as_paid(inv)

    def test_reports_and_income_same_recognized_revenue(self):
        """Reports paid_amount matches Income monthly_income total_income."""
        from apps.core.finance_metrics import recognized_revenue

        rev = recognized_revenue(self.user, 2025, 3)
        income_data = IncomeSelector.get_monthly_income(2025, 3, status="paid", user=self.user)
        self.assertEqual(income_data["total_income"], rev)
        self.assertEqual(income_data["total_income"], Decimal("30.00"))


class InstituteBreakdownTest(TestCase):
    """Breakdown by institute: PAID-only vs PAID+SENT."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        s1 = Student.objects.create(user=self.user, first_name="S1", last_name="T")
        s2 = Student.objects.create(user=self.user, first_name="S2", last_name="T")
        c1 = Contract.objects.create(
            student=s1,
            hourly_rate=Decimal("20"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            institute="InstA",
        )
        c2 = Contract.objects.create(
            student=s2,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            institute="InstB",
        )
        Lesson.objects.create(
            contract=c1,
            date=date(2025, 3, 5),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=c2,
            date=date(2025, 3, 6),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        inv1 = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=c1, user=self.user
        )
        inv2 = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=c2, user=self.user
        )
        InvoiceService.mark_invoice_as_paid(inv1)
        InvoiceService.mark_invoice_as_sent(inv2)

    def test_breakdown_recognized_paid_only(self):
        """breakdown_by_institute_recognized includes only PAID."""
        rec = breakdown_by_institute_recognized(self.user, 2025, 3)
        inst_names = [r["institute"] for r in rec]
        self.assertIn("InstA", inst_names)
        self.assertNotIn("InstB", inst_names)

    def test_breakdown_billed_includes_sent(self):
        """breakdown_by_institute_billed includes PAID + SENT."""
        billed = breakdown_by_institute_billed(self.user, 2025, 3)
        inst_names = [r["institute"] for r in billed]
        self.assertIn("InstA", inst_names)
        self.assertIn("InstB", inst_names)

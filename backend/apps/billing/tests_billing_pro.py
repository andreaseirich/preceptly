"""
Tests for Billing Pro (Premium): invoice numbering, status filter.
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


class BillingProTest(TestCase):
    """Premium invoice numbering and filters."""

    def setUp(self):
        self.basic_user = User.objects.create_user(username="basic", password="test")
        UserProfile.objects.create(user=self.basic_user, is_premium=False)
        self.premium_user = User.objects.create_user(username="premium", password="test")
        UserProfile.objects.create(user=self.premium_user, is_premium=True)

        for user in (self.basic_user, self.premium_user):
            student = Student.objects.create(user=user, first_name="A", last_name="B")
            contract = Contract.objects.create(
                student=student,
                hourly_rate=Decimal("30"),
                unit_duration_minutes=60,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
                is_active=True,
            )
            Lesson.objects.create(
                contract=contract,
                date=date(2025, 3, 5),
                start_time=time(14, 0),
                duration_minutes=60,
                status="taught",
            )

    def test_premium_invoice_gets_number(self):
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), user=self.premium_user
        )
        self.assertIsNotNone(invoice.invoice_number)
        self.assertTrue(invoice.invoice_number.startswith("INV-"))

    def test_basic_invoice_no_number(self):
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), user=self.basic_user
        )
        self.assertIsNone(invoice.invoice_number)

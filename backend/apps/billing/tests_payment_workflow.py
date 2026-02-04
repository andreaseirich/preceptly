"""
Tests for payment workflow: mark paid, undo paid, multi-user isolation.
"""

from datetime import date, time
from decimal import Decimal

from apps.billing.models import Invoice, InvoiceItem
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class PaymentWorkflowTest(TestCase):
    """Mark paid sets paid_at and updates lessons; undo recomputes."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.other = User.objects.create_user(username="other", password="test")
        self.student = Student.objects.create(user=self.user, first_name="A", last_name="Student")
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 5),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=self.contract, user=self.user
        )

    def test_mark_paid_sets_paid_at_and_lesson_paid(self):
        """Mark paid sets invoice.paid_at and lessons remain paid."""
        self.client.login(username="tutor", password="test")
        response = self.client.post(
            reverse("billing:invoice_mark_paid", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")
        self.assertIsNotNone(self.invoice.paid_at)
        for item in self.invoice.items.all():
            if item.lesson:
                self.assertEqual(item.lesson.status, "paid")

    def test_undo_paid_recomputes_lesson_status(self):
        """Undo paid sets lessons back to taught."""
        InvoiceService.mark_invoice_as_paid(self.invoice)
        for item in self.invoice.items.all():
            if item.lesson:
                self.assertEqual(item.lesson.status, "paid")
        self.client.login(username="tutor", password="test")
        response = self.client.post(
            reverse("billing:invoice_undo_paid", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertNotEqual(self.invoice.status, "paid")
        self.assertIsNone(self.invoice.paid_at)
        for item in self.invoice.items.all():
            if item.lesson:
                self.assertEqual(item.lesson.status, "taught")

    def test_other_user_cannot_mark_paid_returns_404(self):
        """Non-owner cannot mark invoice paid."""
        self.client.login(username="other", password="test")
        response = self.client.post(
            reverse("billing:invoice_mark_paid", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 404)


class MultipleInvoicesSameLessonTest(TestCase):
    """Lesson in multiple invoices: paid only when all paid."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.student = Student.objects.create(user=self.user, first_name="A", last_name="Student")
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 5),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.inv1 = Invoice.objects.create(
            owner=self.user,
            payer_name="Test",
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 15),
            status="draft",
        )
        InvoiceItem.objects.create(
            invoice=self.inv1,
            lesson=self.lesson,
            description="Lesson",
            date=self.lesson.date,
            duration_minutes=60,
            amount=Decimal("30"),
        )
        self.inv2 = Invoice.objects.create(
            owner=self.user,
            payer_name="Test",
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
            status="draft",
        )
        InvoiceItem.objects.create(
            invoice=self.inv2,
            lesson=self.lesson,
            description="Same lesson",
            date=self.lesson.date,
            duration_minutes=60,
            amount=Decimal("30"),
        )

    def test_lesson_paid_only_when_all_invoices_paid(self):
        """When one invoice is paid but another is not, lesson stays taught.
        When both are paid, lesson becomes paid."""
        InvoiceService.mark_invoice_as_paid(self.inv1)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, "taught")
        InvoiceService.mark_invoice_as_paid(self.inv2)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, "paid")

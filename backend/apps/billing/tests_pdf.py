"""
Tests for invoice PDF export.
"""

from datetime import date, time
from decimal import Decimal

from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class InvoicePDFTest(TestCase):
    """Tests for invoice PDF generate and download."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.other = User.objects.create_user(username="other", password="test")
        self.student = Student.objects.create(
            user=self.user, first_name="Test", last_name="Student"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        self.invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=self.contract, user=self.user
        )

    def test_pdf_generate_returns_200_and_sets_invoice_pdf(self):
        """Generate endpoint returns 302 redirect and sets invoice.invoice_pdf."""
        self.client.login(username="tutor", password="test")
        response = self.client.post(
            reverse("billing:invoice_pdf_generate", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertTrue(bool(self.invoice.invoice_pdf))
        self.assertIsNotNone(self.invoice.invoice_pdf_created_at)

    def test_pdf_download_returns_application_pdf(self):
        """Download endpoint returns application/pdf."""
        self.client.login(username="tutor", password="test")
        response = self.client.get(
            reverse("billing:invoice_pdf_download", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response.get("Content-Disposition", ""))

    def test_pdf_download_404_for_other_user(self):
        """Non-owner cannot download invoice PDF (404)."""
        self.client.login(username="other", password="test")
        response = self.client.get(
            reverse("billing:invoice_pdf_download", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_pdf_generate_404_for_other_user(self):
        """Non-owner cannot generate invoice PDF (404)."""
        self.client.login(username="other", password="test")
        response = self.client.post(
            reverse("billing:invoice_pdf_generate", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_pdf_generate_idempotent(self):
        """Generating twice does not crash; overwrites same file."""
        self.client.login(username="tutor", password="test")
        r1 = self.client.post(
            reverse("billing:invoice_pdf_generate", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(r1.status_code, 302)
        self.invoice.refresh_from_db()
        path1 = self.invoice.invoice_pdf.name if self.invoice.invoice_pdf else None
        r2 = self.client.post(
            reverse("billing:invoice_pdf_generate", kwargs={"pk": self.invoice.pk})
        )
        self.assertEqual(r2.status_code, 302)
        self.invoice.refresh_from_db()
        path2 = self.invoice.invoice_pdf.name if self.invoice.invoice_pdf else None
        self.assertEqual(path1, path2)

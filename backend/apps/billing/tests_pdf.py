"""
Tests for invoice PDF export.
"""

import os
import tempfile
from datetime import date, time
from decimal import Decimal

from apps.billing.models import Invoice
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
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


class InvoicePDFCleanupTest(TestCase):
    """Tests for PDF file cleanup on delete and regenerate."""

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.user = User.objects.create_user(username="tutor", password="test")
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

    def test_cleanup_command_dry_run_with_orphans(self):
        """Command dry-run reports orphan files without deleting."""
        from io import StringIO

        from django.core.management import call_command

        with override_settings(MEDIA_ROOT=self.media_root):
            orphan_dir = os.path.join(self.media_root, "invoices_pdf", "99", "99")
            os.makedirs(orphan_dir, exist_ok=True)
            orphan_path = os.path.join(orphan_dir, "invoice.pdf")
            with open(orphan_path, "wb") as f:
                f.write(b"fake pdf")
            out = StringIO()
            call_command("cleanup_orphan_invoice_pdfs", "--dry-run", stdout=out)
            self.assertIn("Would delete", out.getvalue())
            self.assertIn("invoice.pdf", out.getvalue())
            self.assertTrue(os.path.exists(orphan_path))

    @override_settings(MEDIA_ROOT=None)
    def test_cleanup_without_media_root(self):
        """Command exits safely when MEDIA_ROOT is not configured."""
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("cleanup_orphan_invoice_pdfs", "--dry-run", stdout=out)
        self.assertIn("MEDIA_ROOT", out.getvalue())

    def test_delete_invoice_removes_pdf_file(self):
        """Deleting an invoice deletes its PDF file from storage."""
        with override_settings(MEDIA_ROOT=self.media_root):
            invoice = InvoiceService.create_invoice_from_lessons(
                date(2025, 3, 1),
                date(2025, 3, 31),
                contract=self.contract,
                user=self.user,
            )
            self.client.login(username="tutor", password="test")
            self.client.post(reverse("billing:invoice_pdf_generate", kwargs={"pk": invoice.pk}))
            invoice.refresh_from_db()
            self.assertTrue(bool(invoice.invoice_pdf))
            pdf_path = invoice.invoice_pdf.path
            self.assertTrue(os.path.exists(pdf_path))
            invoice.delete()
            self.assertFalse(os.path.exists(pdf_path))

    def test_regenerate_keeps_single_file_reference(self):
        """Regenerating PDF overwrites the same file; only one DB reference."""
        with override_settings(MEDIA_ROOT=self.media_root):
            invoice = InvoiceService.create_invoice_from_lessons(
                date(2025, 3, 1),
                date(2025, 3, 31),
                contract=self.contract,
                user=self.user,
            )
            self.client.login(username="tutor", password="test")
            self.client.post(reverse("billing:invoice_pdf_generate", kwargs={"pk": invoice.pk}))
            invoice.refresh_from_db()
            path1 = invoice.invoice_pdf.name
            self.client.post(reverse("billing:invoice_pdf_generate", kwargs={"pk": invoice.pk}))
            invoice.refresh_from_db()
            path2 = invoice.invoice_pdf.name
            self.assertEqual(path1, path2)
            self.assertEqual(
                Invoice.objects.filter(invoice_pdf__isnull=False).exclude(invoice_pdf="").count(),
                1,
            )

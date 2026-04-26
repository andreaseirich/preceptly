"""
Tests für Management Commands der Billing-App.
"""

from datetime import date, time
from decimal import Decimal
from io import StringIO

from apps.billing.models import Invoice, InvoiceItem
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import User


class ResetPaidLessonsCommandTest(TestCase):
    """Tests für reset_paid_lessons Management Command."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Max", last_name="Mustermann", email="max@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_reset_paid_lessons_without_invoices(self):
        """Test: reset_paid_lessons setzt PAID Lessons auf TAUGHT zurück."""
        # Erstelle Lessons mit verschiedenen Status
        paid_lesson1 = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )
        paid_lesson2 = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 16),
            start_time=time(15, 0),
            duration_minutes=60,
            status="paid",
        )
        taught_lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 17),
            start_time=time(16, 0),
            duration_minutes=60,
            status="taught",
        )

        # Rufe Command auf
        out = StringIO()
        call_command("reset_paid_lessons", stdout=out)

        # Prüfe, dass PAID Lessons auf TAUGHT gesetzt wurden
        paid_lesson1.refresh_from_db()
        paid_lesson2.refresh_from_db()
        taught_lesson.refresh_from_db()

        self.assertEqual(paid_lesson1.status, "taught")
        self.assertEqual(paid_lesson2.status, "taught")
        self.assertEqual(taught_lesson.status, "taught")  # Unverändert

    def test_reset_paid_lessons_with_invoices(self):
        """Test: reset_paid_lessons mit --delete-invoices löscht auch Rechnungen."""
        # Erstelle Lesson und Rechnung
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Prüfe, dass Lesson auf PAID gesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "paid")

        # Rufe Command mit --delete-invoices auf
        out = StringIO()
        call_command("reset_paid_lessons", "--delete-invoices", stdout=out)

        # Prüfe, dass Lesson auf TAUGHT zurückgesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")

        # Prüfe, dass Rechnung gelöscht wurde
        self.assertFalse(Invoice.objects.filter(pk=invoice.pk).exists())
        self.assertFalse(InvoiceItem.objects.filter(invoice=invoice).exists())

    def test_reset_paid_lessons_dry_run(self):
        """Test: --dry-run zeigt nur an, was geändert würde."""
        # Erstelle PAID Lesson
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )

        # Rufe Command mit --dry-run auf
        out = StringIO()
        call_command("reset_paid_lessons", "--dry-run", stdout=out)
        output = out.getvalue()

        # Prüfe, dass Lesson NICHT geändert wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "paid")

        # Prüfe, dass Output Informationen enthält
        self.assertIn("DRY RUN", output)
        self.assertIn("Lesson", output)

    def test_reset_paid_lessons_no_paid_lessons(self):
        """Test: Command gibt Meldung aus, wenn keine PAID Lessons gefunden werden."""
        # Erstelle nur TAUGHT Lessons
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Rufe Command auf
        out = StringIO()
        call_command("reset_paid_lessons", stdout=out)
        output = out.getvalue()

        # Prüfe, dass entsprechende Meldung ausgegeben wird
        self.assertIn("Keine Lessons mit Status PAID gefunden", output)

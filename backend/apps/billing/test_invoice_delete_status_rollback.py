"""
Tests für Status-Rückstellung beim Löschen von Rechnungen.
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.billing.models import Invoice, InvoiceItem
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student


class InvoiceDeleteStatusRollbackTest(TestCase):
    """Tests für Status-Rückstellung beim Löschen von Rechnungen."""

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

    def test_lesson_status_reset_to_taught_when_invoice_deleted(self):
        """Test: Lesson-Status wird auf TAUGHT zurückgesetzt beim Löschen einer Rechnung."""
        # Erstelle Lesson mit Status TAUGHT
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Erstelle Rechnung (setzt Lesson auf PAID)
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Prüfe, dass Lesson auf PAID gesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "paid")

        # Lösche Rechnung über InvoiceService
        reset_count = InvoiceService.delete_invoice(invoice)

        # Prüfe, dass Lesson auf TAUGHT zurückgesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")
        self.assertEqual(reset_count, 1)

        # Prüfe, dass InvoiceItems gelöscht wurden (verwende invoice_id, da invoice gelöscht wurde)
        invoice_id = invoice.pk
        self.assertFalse(InvoiceItem.objects.filter(invoice_id=invoice_id).exists())
        self.assertFalse(Invoice.objects.filter(pk=invoice_id).exists())

    def test_lesson_status_reset_when_invoice_deleted_directly(self):
        """Test: Status-Rückstellung funktioniert auch bei direktem invoice.delete()."""
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

        # Lösche Rechnung direkt (ohne InvoiceService)
        reset_count = invoice.delete()

        # Prüfe, dass Lesson auf TAUGHT zurückgesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")
        self.assertEqual(reset_count, 1)

    def test_multiple_lessons_reset_when_invoice_deleted(self):
        """Test: Mehrere Lessons werden korrekt zurückgesetzt."""
        # Erstelle mehrere Lessons
        lesson1 = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        lesson2 = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 16),
            start_time=time(15, 0),
            duration_minutes=60,
            status="taught",
        )
        lesson3 = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 17),
            start_time=time(16, 0),
            duration_minutes=60,
            status="taught",
        )

        # Erstelle Rechnung mit allen Lessons
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Prüfe, dass alle Lessons auf PAID gesetzt wurden
        lesson1.refresh_from_db()
        lesson2.refresh_from_db()
        lesson3.refresh_from_db()
        self.assertEqual(lesson1.status, "paid")
        self.assertEqual(lesson2.status, "paid")
        self.assertEqual(lesson3.status, "paid")

        # Lösche Rechnung
        reset_count = InvoiceService.delete_invoice(invoice)

        # Prüfe, dass alle Lessons auf TAUGHT zurückgesetzt wurden
        lesson1.refresh_from_db()
        lesson2.refresh_from_db()
        lesson3.refresh_from_db()
        self.assertEqual(lesson1.status, "taught")
        self.assertEqual(lesson2.status, "taught")
        self.assertEqual(lesson3.status, "taught")
        self.assertEqual(reset_count, 3)

    def test_only_paid_lessons_are_reset(self):
        """Test: Nur Lessons mit Status PAID werden zurückgesetzt."""
        # Erstelle Lesson mit Status TAUGHT
        lesson1 = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Erstelle Rechnung (setzt lesson1 auf PAID)
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Manuell eine weitere Lesson mit Status PLANNED erstellen
        # (sollte nicht in Rechnung sein, aber testen wir trotzdem)
        lesson2 = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 20),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe Status vor Löschen
        lesson1.refresh_from_db()
        self.assertEqual(lesson1.status, "paid")
        self.assertEqual(lesson2.status, "planned")

        # Lösche Rechnung
        reset_count = InvoiceService.delete_invoice(invoice)

        # Prüfe, dass nur lesson1 zurückgesetzt wurde
        lesson1.refresh_from_db()
        lesson2.refresh_from_db()
        self.assertEqual(lesson1.status, "taught")
        self.assertEqual(lesson2.status, "planned")  # Unverändert
        self.assertEqual(reset_count, 1)

    def test_invoice_items_deleted_after_invoice_deletion(self):
        """Test: InvoiceItems werden nach Löschen der Rechnung entfernt."""
        # Erstelle Lesson und Rechnung
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Prüfe, dass InvoiceItems existieren
        invoice_items = InvoiceItem.objects.filter(invoice=invoice)
        self.assertEqual(invoice_items.count(), 1)

        # Lösche Rechnung (speichere ID vorher)
        invoice_id = invoice.pk
        InvoiceService.delete_invoice(invoice)

        # Prüfe, dass InvoiceItems gelöscht wurden (CASCADE)
        self.assertFalse(InvoiceItem.objects.filter(invoice_id=invoice_id).exists())
        self.assertFalse(Invoice.objects.filter(pk=invoice_id).exists())

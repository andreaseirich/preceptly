"""
Tests für automatische Rechnungserstellung und Lesson-Eindeutigkeit.
"""

from datetime import date, time
from decimal import Decimal

from apps.billing.models import InvoiceItem
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.test import TestCase
from django.contrib.auth.models import User


class AutomaticInvoiceCreationTest(TestCase):
    """Tests für automatische Rechnungserstellung."""

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

    def test_only_taught_lessons_included(self):
        """Test: Nur Lessons mit Status TAUGHT werden in Rechnung aufgenommen."""
        # Erstelle Lessons mit verschiedenen Status
        taught_lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        planned_lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 16),
            start_time=time(15, 0),
            duration_minutes=60,
            status="planned",
        )
        paid_lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 17),
            start_time=time(16, 0),
            duration_minutes=60,
            status="paid",
        )

        # Erstelle Rechnung
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Nur TAUGHT Lesson sollte in Rechnung sein
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(invoice.items.first().lesson, taught_lesson)

        # Prüfe, dass PLANNED und PAID Lessons nicht aufgenommen wurden
        lesson_ids = [item.lesson_id for item in invoice.items.all() if item.lesson_id]
        self.assertIn(taught_lesson.id, lesson_ids)
        self.assertNotIn(planned_lesson.id, lesson_ids)
        self.assertNotIn(paid_lesson.id, lesson_ids)

    def test_lesson_can_only_be_in_one_invoice(self):
        """Test: Eine Lesson kann nicht in zwei Rechnungen landen."""
        # Erstelle Lesson
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Erstelle erste Rechnung
        invoice1 = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Prüfe, dass Lesson in erster Rechnung ist
        self.assertEqual(invoice1.items.count(), 1)
        self.assertEqual(invoice1.items.first().lesson, lesson)

        # Versuche zweite Rechnung zu erstellen (sollte ValueError werfen, da keine Lessons mehr verfügbar)
        with self.assertRaises(ValueError) as context:
            InvoiceService.create_invoice_from_lessons(
                date(2025, 8, 1), date(2025, 8, 31), self.contract
            )

        # Prüfe, dass die Fehlermeldung korrekt ist
        self.assertIn("No billable lessons found", str(context.exception))

        # Prüfe, dass Lesson immer noch nur in erster Rechnung ist
        self.assertEqual(InvoiceItem.objects.filter(lesson=lesson).count(), 1)

    def test_automatic_selection_all_taught_lessons_in_period(self):
        """Test: Alle TAUGHT Lessons im Zeitraum werden automatisch aufgenommen."""
        # Erstelle mehrere TAUGHT Lessons
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
        # Lesson außerhalb des Zeitraums
        lesson_outside = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 9, 1),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Erstelle Rechnung
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Alle 3 Lessons im Zeitraum sollten aufgenommen sein
        self.assertEqual(invoice.items.count(), 3)
        lesson_ids = [item.lesson_id for item in invoice.items.all() if item.lesson_id]
        self.assertIn(lesson1.id, lesson_ids)
        self.assertIn(lesson2.id, lesson_ids)
        self.assertIn(lesson3.id, lesson_ids)
        self.assertNotIn(lesson_outside.id, lesson_ids)

    def test_lessons_set_to_paid_on_invoice_creation(self):
        """Test: Lessons werden auf PAID gesetzt beim Erstellen einer Rechnung."""
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Erstelle Rechnung
        InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Prüfe, dass Lesson auf PAID gesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "paid")

    def test_lessons_reset_to_taught_on_invoice_deletion(self):
        """Test: Lessons werden auf TAUGHT zurückgesetzt beim Löschen einer Rechnung."""
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        # Erstelle Rechnung
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Prüfe, dass Lesson auf PAID gesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "paid")

        # Lösche Rechnung
        reset_count = InvoiceService.delete_invoice(invoice)

        # Prüfe, dass Lesson auf TAUGHT zurückgesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")
        self.assertEqual(reset_count, 1)

    def test_get_billable_lessons_excludes_already_invoiced(self):
        """Test: get_billable_lessons schließt Lessons aus, die bereits in einer Rechnung sind."""
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 16),
            start_time=time(15, 0),
            duration_minutes=60,
            status="taught",
        )

        # Prüfe, dass beide Lessons vorher verfügbar sind
        billable_before = InvoiceService.get_billable_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract.id
        )
        self.assertEqual(billable_before.count(), 2)

        # Erstelle Rechnung (beide Lessons sollten aufgenommen werden)
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Prüfe, dass beide in Rechnung sind
        self.assertEqual(invoice.items.count(), 2)

        # Nach Erstellung sollten beide nicht mehr in get_billable_lessons erscheinen
        billable_after = InvoiceService.get_billable_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract.id
        )

        # Keine Lessons sollten mehr verfügbar sein
        self.assertEqual(billable_after.count(), 0)

"""
Tests für Einnahmenberechnung und Formatierung.
"""

from datetime import date, time
from decimal import Decimal

from apps.billing.models import Invoice, InvoiceItem
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.core.selectors import IncomeSelector
from apps.core.templatetags.currency import euro
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase


class IncomeCalculationTest(TestCase):
    """Tests für korrekte Einnahmenberechnung (gleiche Logik wie InvoiceService)."""

    def setUp(self):
        self.student = Student.objects.create(
            first_name="Max", last_name="Mustermann", email="max@example.com"
        )
        # Vertrag: 45 Min/Einheit, 12€/Einheit
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("12.00"),
            unit_duration_minutes=45,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_income_calculation_matches_invoice_calculation(self):
        """Test: Einnahmenberechnung verwendet gleiche Logik wie InvoiceService."""
        # Erstelle Lesson mit 90 Minuten
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=90,
            status="taught",
        )

        # Berechne mit IncomeSelector
        income_amount = IncomeSelector._calculate_lesson_amount(lesson)

        # Erstelle Rechnung und prüfe InvoiceItem-Betrag
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        invoice_item = invoice.items.first()

        # Beträge sollten identisch sein
        # 90 Min / 45 Min = 2 Einheiten, 2 * 12€ = 24€
        self.assertEqual(income_amount, Decimal("24.00"))
        self.assertEqual(invoice_item.amount, Decimal("24.00"))
        self.assertEqual(income_amount, invoice_item.amount)

    def test_income_uses_invoice_item_amount_when_available(self):
        """Test: Für Lessons in Rechnungen wird Betrag aus InvoiceItem verwendet."""
        # Erstelle Lesson und Rechnung
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=90,
            status="taught",
        )

        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        invoice_item = invoice.items.first()

        # Verwende _get_lesson_amount (sollte InvoiceItem-Betrag verwenden)
        income_amount = IncomeSelector._get_lesson_amount(lesson)

        # Sollte identisch mit InvoiceItem-Betrag sein
        self.assertEqual(income_amount, invoice_item.amount)

    def test_monthly_income_matches_invoice_total(self):
        """Test: Monatliche Einnahmen stimmen mit Rechnungssumme überein."""
        # Erstelle mehrere Lessons
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=90,  # 2 Einheiten = 24€
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 16),
            start_time=time(15, 0),
            duration_minutes=45,  # 1 Einheit = 12€
            status="taught",
        )

        # Erstelle Rechnung
        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Berechne monatliche Einnahmen
        monthly_income = IncomeSelector.get_monthly_income(2025, 8, status="paid")

        # Einnahmen sollten identisch mit Rechnungssumme sein
        # 24€ + 12€ = 36€
        self.assertEqual(monthly_income["total_income"], invoice.total_amount)
        self.assertEqual(monthly_income["total_income"], Decimal("36.00"))

    def test_income_by_status_uses_correct_calculation(self):
        """Test: Einnahmen nach Status verwenden korrekte Berechnung."""
        # Erstelle Lessons mit verschiedenen Status
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=90,  # 2 Einheiten = 24€
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 16),
            start_time=time(15, 0),
            duration_minutes=45,  # 1 Einheit = 12€
            status="planned",
        )

        # Berechne Einnahmen nach Status
        income_by_status = IncomeSelector.get_income_by_status(year=2025, month=8)

        # Prüfe, dass TAUGHT-Lessons korrekt berechnet werden
        self.assertEqual(income_by_status["taught"]["income"], Decimal("24.00"))
        self.assertEqual(income_by_status["planned"]["income"], Decimal("12.00"))

    def test_billing_status_uses_invoice_item_amounts(self):
        """Test: Abrechnungsstatus verwendet Beträge aus InvoiceItems."""
        # Erstelle Lesson und Rechnung
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=90,  # 2 Einheiten = 24€
            status="taught",
        )

        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), self.contract
        )

        # Berechne Abrechnungsstatus
        billing_status = IncomeSelector.get_billing_status(year=2025, month=8)

        # Abgerechnete Einnahmen sollten identisch mit Rechnungssumme sein
        self.assertEqual(billing_status["invoiced"]["income"], invoice.total_amount)
        self.assertEqual(billing_status["invoiced"]["income"], Decimal("24.00"))
        self.assertEqual(billing_status["not_invoiced"]["income"], Decimal("0.00"))

    def test_get_lesson_amount_sums_all_invoice_lines_for_same_lesson(self):
        """Regression: multiple InvoiceItems for one lesson must all count (not .first() only)."""
        user = User.objects.create_user(username="tutor_sum", password="x")
        student = Student.objects.create(user=user, first_name="A", last_name="B")
        contract = Contract.objects.create(
            student=student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        lesson = Lesson.objects.create(
            contract=contract,
            date=date(2025, 8, 10),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        inv1 = Invoice.objects.create(
            owner=user,
            payer_name="P",
            period_start=date(2025, 8, 1),
            period_end=date(2025, 8, 31),
            status="draft",
        )
        InvoiceItem.objects.create(
            invoice=inv1,
            lesson=lesson,
            description="Line A",
            date=lesson.date,
            duration_minutes=60,
            amount=Decimal("10.00"),
        )
        inv2 = Invoice.objects.create(
            owner=user,
            payer_name="P",
            period_start=date(2025, 8, 1),
            period_end=date(2025, 8, 31),
            status="draft",
        )
        InvoiceItem.objects.create(
            invoice=inv2,
            lesson=lesson,
            description="Line B",
            date=lesson.date,
            duration_minutes=60,
            amount=Decimal("20.00"),
        )
        self.assertEqual(IncomeSelector._get_lesson_amount(lesson), Decimal("30.00"))


class EuroFormattingTest(TestCase):
    """Tests für Euro-Formatierung."""

    def test_euro_filter_formats_correctly(self):
        """Test: Euro-Filter formatiert korrekt."""
        # Test verschiedene Werte
        self.assertEqual(euro(Decimal("90")), "90,00 €")
        self.assertEqual(euro(Decimal("544")), "544,00 €")
        self.assertEqual(euro(Decimal("90.5")), "90,50 €")
        self.assertEqual(euro(Decimal("1234.56")), "1.234,56 €")
        self.assertEqual(euro(Decimal("0")), "0,00 €")
        self.assertEqual(euro(Decimal("0.01")), "0,01 €")

    def test_euro_filter_handles_none(self):
        """Test: Euro-Filter behandelt None korrekt."""
        self.assertEqual(euro(None), "0,00 €")

    def test_euro_filter_handles_strings(self):
        """Test: Euro-Filter konvertiert Strings korrekt."""
        self.assertEqual(euro("90"), "90,00 €")
        self.assertEqual(euro("544.50"), "544,50 €")

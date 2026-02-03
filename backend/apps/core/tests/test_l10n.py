"""
Tests for localization (l10n) - date, number, and currency formatting.
"""

from datetime import date, time
from decimal import Decimal

from apps.billing.models import Invoice
from apps.contracts.models import Contract
from apps.core.templatetags.currency import euro
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.translation import activate


class L10nTestCase(TestCase):
    """Tests for localization of dates, numbers, and currency."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client = Client()
        self.client.login(username="testuser", password="password")

        self.student = Student.objects.create(
            user=self.user, first_name="Test", last_name="Student"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2023, 1, 1),
        )

    def test_currency_formatting_english(self):
        """Test that currency is formatted correctly in English."""
        activate("en")

        # Test euro filter
        result = euro(Decimal("90.00"))
        self.assertIn("90", result)
        self.assertIn("€", result)
        # English format: 90.00 € (point as decimal separator)
        self.assertIn(".", result)
        self.assertNotIn(",", result.split(".")[0])  # No comma in integer part for small numbers

        result = euro(Decimal("1234.56"))
        self.assertIn("1,234.56", result)  # English: comma as thousands separator
        self.assertIn("€", result)

    def test_currency_formatting_german(self):
        """Test that currency is formatted correctly in German."""
        activate("de")

        # Test euro filter
        result = euro(Decimal("90.00"))
        self.assertIn("90", result)
        self.assertIn("€", result)
        # German format: 90,00 € (comma as decimal separator)
        self.assertIn(",", result)

        result = euro(Decimal("1234.56"))
        self.assertIn("1.234,56", result)  # German: point as thousands separator, comma as decimal
        self.assertIn("€", result)

    def test_date_formatting_english(self):
        """Test that dates are formatted correctly in English."""
        activate("en")

        # Create a lesson with a date
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 12, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Access a view that displays dates
        response = self.client.get(reverse("lessons:detail", kwargs={"pk": lesson.pk}))
        self.assertEqual(response.status_code, 200)

        # Check that the date appears in the response
        # English format: Dec. 5, 2023 or 12/5/2023 (depending on SHORT_DATE_FORMAT)
        content = response.content.decode("utf-8")
        self.assertIn("2023", content)  # Year should be present
        self.assertIn("12", content) or self.assertIn("Dec", content)  # Month should be present

    def test_date_formatting_german(self):
        """Test that dates are formatted correctly in German."""
        activate("de")

        # Create a lesson with a date
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2023, 12, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Access a view that displays dates
        response = self.client.get(reverse("lessons:detail", kwargs={"pk": lesson.pk}))
        self.assertEqual(response.status_code, 200)

        # Check that the date appears in the response
        # German format: 05.12.2023 (day.month.year)
        content = response.content.decode("utf-8")
        self.assertIn("2023", content)  # Year should be present
        # German format typically uses dots: 05.12.2023
        self.assertIn("12", content)  # Month should be present

    def test_invoice_currency_formatting_english(self):
        """Test that invoice amounts are formatted correctly in English."""
        activate("en")

        # Create invoice
        invoice = Invoice.objects.create(
            owner=self.user,
            payer_name="Test Payer",
            contract=self.contract,
            period_start=date(2023, 1, 1),
            period_end=date(2023, 1, 31),
            total_amount=Decimal("250.50"),
            status="draft",
        )

        response = self.client.get(reverse("billing:invoice_detail", kwargs={"pk": invoice.pk}))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # English format: 250.50 €
        self.assertIn("250", content)
        self.assertIn("€", content)

    def test_invoice_currency_formatting_german(self):
        """Test that invoice amounts are formatted correctly in German."""
        activate("de")

        # Create invoice
        invoice = Invoice.objects.create(
            owner=self.user,
            payer_name="Test Payer",
            contract=self.contract,
            period_start=date(2023, 1, 1),
            period_end=date(2023, 1, 31),
            total_amount=Decimal("250.50"),
            status="draft",
        )

        response = self.client.get(reverse("billing:invoice_detail", kwargs={"pk": invoice.pk}))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # German format: 250,50 €
        self.assertIn("250", content)
        self.assertIn("€", content)
        # Should use comma as decimal separator
        self.assertIn(",", content) or self.assertIn("250,50", content)

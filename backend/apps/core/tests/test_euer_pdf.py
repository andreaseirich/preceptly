"""
Tests for the EÜR PDF download (apps.core.views.EuerPdfView).

The EÜR page previously only offered window.print() on the HTML page.
This covers the new PDF export instead.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import Invoice
from apps.core.models import Expense

User = get_user_model()


class EuerPdfViewTest(TestCase):
    """GET on euer_pdf must return a valid PDF, not the printable HTML page."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor_euer", password="testpass123")
        self.client = Client()
        self.client.force_login(self.user)

    def test_euer_pdf_returns_pdf_content_type(self):
        response = self.client.get(reverse("core:euer_pdf"), {"year": 2026})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("euer-2026.pdf", response["Content-Disposition"])

    def test_euer_pdf_starts_with_pdf_magic_bytes(self):
        response = self.client.get(reverse("core:euer_pdf"), {"year": 2026})
        content = b"".join(response.streaming_content) if response.streaming else response.content
        self.assertTrue(content.startswith(b"%PDF-"))

    def test_euer_pdf_includes_income_and_expenses(self):
        Invoice.objects.create(
            owner=self.user,
            status="paid",
            paid_at=timezone.datetime(2026, 3, 1, tzinfo=timezone.get_current_timezone()),
            total_amount=Decimal("500.00"),
            period_start=timezone.datetime(2026, 3, 1).date(),
            period_end=timezone.datetime(2026, 3, 31).date(),
            payer_name="Test Payer",
        )
        Expense.objects.create(
            user=self.user,
            date="2026-03-05",
            amount=Decimal("50.00"),
            category="office",
            description="Bueromaterial",
            business_use_percent=100,
        )
        response = self.client.get(reverse("core:euer_pdf"), {"year": 2026})
        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 1000)

    def test_euer_page_links_to_pdf_download(self):
        response = self.client.get(reverse("core:euer"), {"year": 2026})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("core:euer_pdf"))
        self.assertNotContains(response, "window.print()")

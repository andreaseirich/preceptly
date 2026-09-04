"""
Regression test for generate_euer_pdf: exercises the loss/profit color
branch so a broken reference to _COLOR_LOSS/_COLOR_DARK (e.g. a typo in
the hexval() conversion) fails loudly instead of only showing up as a
CodeQL "unused variable" note.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.core.pdf_service import generate_euer_pdf


class GenerateEuerPdfColorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pdftester", password="pass")

    def test_generates_pdf_bytes_for_a_loss(self):
        pdf_bytes = generate_euer_pdf(
            user=self.user,
            year=2026,
            total_income=Decimal("1000.00"),
            expenses_by_category={"Miete": Decimal("1500.00")},
            total_expenses=Decimal("1500.00"),
            profit=Decimal("-500.00"),
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_generates_pdf_bytes_for_a_profit(self):
        pdf_bytes = generate_euer_pdf(
            user=self.user,
            year=2026,
            total_income=Decimal("2000.00"),
            expenses_by_category={"Miete": Decimal("500.00")},
            total_expenses=Decimal("500.00"),
            profit=Decimal("1500.00"),
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

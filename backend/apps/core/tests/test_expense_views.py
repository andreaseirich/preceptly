"""
Tests for expense views (Steuern/Ausgaben).

Regression test for a bug where expense_form.html referenced an undefined
template filter ("add_class"), causing a TemplateSyntaxError -> HTTP 500
on every render of the New/Edit expense form.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class ExpenseFormViewTest(TestCase):
    """New/Edit expense form must render without a server error."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor_expense", password="testpass123")
        self.client = Client()
        self.client.force_login(self.user)

    def test_new_expense_form_renders(self):
        """GET on expense_create must return 200, not 500."""
        response = self.client.get(reverse("core:expense_create"))
        self.assertEqual(response.status_code, 200)

    def test_new_expense_can_be_created(self):
        """POST with valid data creates an expense and redirects."""
        response = self.client.post(
            reverse("core:expense_create"),
            {
                "date": "2026-07-01",
                "amount": "42.50",
                "category": "office",
                "description": "Testausgabe",
                "notes": "",
                "business_use_percent": "100",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.user.expenses.filter(description="Testausgabe").exists())

    def test_edit_expense_form_renders(self):
        """GET on expense_update must return 200, not 500."""
        expense = self.user.expenses.create(
            date="2026-07-01",
            amount="10.00",
            category="other",
            description="Bestehende Ausgabe",
            business_use_percent=100,
        )
        response = self.client.get(reverse("core:expense_update", args=[expense.pk]))
        self.assertEqual(response.status_code, 200)

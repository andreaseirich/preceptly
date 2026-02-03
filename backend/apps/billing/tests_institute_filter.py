"""
Tests for institute filter in invoice creation.
"""

import re
from datetime import date, time
from decimal import Decimal

from apps.billing.forms import InvoiceCreateForm, _get_institute_choices_for_user
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase


class InstituteFilterTest(TestCase):
    """Tests for institute filter in invoice creation."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.student_a = Student.objects.create(
            user=self.user,
            first_name="Anna",
            last_name="Schmidt",
            email="anna@example.com",
        )
        self.student_b = Student.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mueller",
            email="max@example.com",
        )
        self.contract_a = Contract.objects.create(
            student=self.student_a,
            institute="Institut Alpha",
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_b = Contract.objects.create(
            student=self.student_b,
            institute="Institut Beta",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_private = Contract.objects.create(
            student=self.student_a,
            institute=None,
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_institute_choices_include_only_tutor_institutes(self):
        """Invoice form lists only institutes from tutor's contracts."""
        choices = _get_institute_choices_for_user(self.user)
        self.assertIn(("", "All institutes"), choices)
        self.assertIn(("Institut Alpha", "Institut Alpha"), choices)
        self.assertIn(("Institut Beta", "Institut Beta"), choices)
        # Private contracts (institute=None) should not appear
        self.assertEqual(len(choices), 3)

    def test_institute_filter_limits_billable_lessons(self):
        """get_billable_lessons filters by institute when specified."""
        Lesson.objects.create(
            contract=self.contract_a,
            date=date(2025, 3, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract_b,
            date=date(2025, 3, 6),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        period_start = date(2025, 3, 1)
        period_end = date(2025, 3, 31)

        all_lessons = InvoiceService.get_billable_lessons(period_start, period_end, user=self.user)
        self.assertEqual(all_lessons.count(), 2)

        alpha_lessons = InvoiceService.get_billable_lessons(
            period_start, period_end, institute="Institut Alpha", user=self.user
        )
        self.assertEqual(alpha_lessons.count(), 1)
        self.assertEqual(alpha_lessons.first().contract.institute, "Institut Alpha")

        beta_lessons = InvoiceService.get_billable_lessons(
            period_start, period_end, institute="Institut Beta", user=self.user
        )
        self.assertEqual(beta_lessons.count(), 1)
        self.assertEqual(beta_lessons.first().contract.institute, "Institut Beta")

    def test_invoice_create_view_renders_institute_filter(self):
        """Invoice create page shows institute dropdown."""
        response = self.client.get("/billing/create/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Institute (optional)", content)
        self.assertIn("Institut Alpha", content)
        self.assertIn("Institut Beta", content)

    def test_institute_filter_restricts_contract_dropdown(self):
        """When institute is selected, contract dropdown shows only matching contracts."""
        form = InvoiceCreateForm(user=self.user, initial={"institute": "Institut Alpha"})
        contract_ids = list(form.fields["contract"].queryset.values_list("pk", flat=True))
        self.assertEqual(len(contract_ids), 1)
        self.assertEqual(contract_ids[0], self.contract_a.pk)

    def test_empty_institute_shows_no_lessons_gracefully(self):
        """Selecting institute with no lessons shows empty state, no 500."""
        response = self.client.get(
            "/billing/create/",
            {
                "period_start": "2025-03-01",
                "period_end": "2025-03-31",
                "institute": "Institut Alpha",
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("No billable lessons", content)

    def test_create_invoice_with_institute_filter(self):
        """Invoice creation with institute filter includes only matching lessons."""
        Lesson.objects.create(
            contract=self.contract_a,
            date=date(2025, 4, 10),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract_b,
            date=date(2025, 4, 11),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        get_resp = self.client.get("/billing/create/")
        match = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            get_resp.content.decode(),
        )
        csrf = match.group(1) if match else ""
        response = self.client.post(
            "/billing/create/",
            {
                "period_start": "2025-04-01",
                "period_end": "2025-04-30",
                "institute": "Institut Alpha",
                "contract": "",
                "csrfmiddlewaretoken": csrf,
            },
        )
        self.assertEqual(response.status_code, 302)
        from apps.billing.models import Invoice

        invoice = Invoice.objects.filter(contract=self.contract_a).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(invoice.payer_name, "Institut Alpha")

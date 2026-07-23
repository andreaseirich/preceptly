"""
Tests for institute filter in invoice creation.
"""

import re
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils.translation import override as translation_override

from apps.billing.forms import (
    NO_INSTITUTE_FILTER_VALUE,
    InvoiceCreateForm,
    _get_institute_choices_for_user,
)
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract, Institute
from apps.lessons.models import Lesson


class InstituteFilterTest(TestCase):
    """Tests for institute filter in invoice creation."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.student_a = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Anna",
            last_name="Schmidt",
            email="anna@example.com",
        )
        self.student_b = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Max",
            last_name="Mueller",
            email="max@example.com",
        )
        self.institute_alpha = Institute.objects.create(
            user=self.user, institute_name="Institut Alpha"
        )
        self.institute_beta = Institute.objects.create(
            user=self.user, institute_name="Institut Beta"
        )
        self.contract_a = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            institute_fk=self.institute_alpha,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_b = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            institute_fk=self.institute_beta,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_private = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            institute_fk=None,
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_institute_choices_include_only_tutor_institutes(self):
        """Invoice form lists only the tutor's institutes, plus an explicit
        "no institute" bucket for private contracts."""
        with translation_override("en"):
            choices = _get_institute_choices_for_user(self.user)
        self.assertIn(("", "All institutes"), choices)
        self.assertIn((NO_INSTITUTE_FILTER_VALUE, "No institute (private lessons)"), choices)
        self.assertIn((str(self.institute_alpha.pk), "Institut Alpha"), choices)
        self.assertIn((str(self.institute_beta.pk), "Institut Beta"), choices)
        self.assertEqual(len(choices), 4)

    def test_no_institute_choice_absent_without_private_contracts(self):
        """The "no institute" bucket only appears when the tutor actually has private
        (institute-less) contracts."""
        Contract.objects.filter(user=self.user, institute_fk__isnull=True).delete()
        with translation_override("en"):
            choices = _get_institute_choices_for_user(self.user)
        choice_values = [value for value, _label in choices]
        self.assertNotIn(NO_INSTITUTE_FILTER_VALUE, choice_values)

    def test_no_institute_filter_limits_billable_lessons_to_private_contracts(self):
        """Selecting "no institute" only bills lessons from private (institute-less) contracts."""
        Lesson.objects.create(
            contract=self.contract_a,
            date=date(2025, 3, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract_private,
            date=date(2025, 3, 6),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        period_start = date(2025, 3, 1)
        period_end = date(2025, 3, 31)

        private_lessons = InvoiceService.get_billable_lessons(
            period_start, period_end, institute=NO_INSTITUTE_FILTER_VALUE, user=self.user
        )
        self.assertEqual(private_lessons.count(), 1)
        self.assertEqual(private_lessons.first().contract, self.contract_private)

    def test_no_institute_filter_restricts_contract_dropdown(self):
        """When "no institute" is selected, the contract dropdown only shows private contracts."""
        form = InvoiceCreateForm(user=self.user, initial={"institute": NO_INSTITUTE_FILTER_VALUE})
        contract_ids = set(form.fields["contract"].queryset.values_list("pk", flat=True))
        self.assertIn(self.contract_private.pk, contract_ids)
        self.assertNotIn(self.contract_a.pk, contract_ids)
        self.assertNotIn(self.contract_b.pk, contract_ids)

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
            period_start, period_end, institute=self.institute_alpha.pk, user=self.user
        )
        self.assertEqual(alpha_lessons.count(), 1)
        self.assertEqual(alpha_lessons.first().contract.institute, "Institut Alpha")

        beta_lessons = InvoiceService.get_billable_lessons(
            period_start, period_end, institute=self.institute_beta.pk, user=self.user
        )
        self.assertEqual(beta_lessons.count(), 1)
        self.assertEqual(beta_lessons.first().contract.institute, "Institut Beta")

    def test_invoice_create_view_renders_institute_filter(self):
        """Invoice create page shows institute dropdown."""
        response = self.client.get("/billing/create/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Institut", content)
        self.assertIn("Institut Alpha", content)
        self.assertIn("Institut Beta", content)

    def test_institute_filter_restricts_contract_dropdown(self):
        """When institute is selected, contract dropdown shows only matching contracts."""
        form = InvoiceCreateForm(
            user=self.user, initial={"institute": str(self.institute_alpha.pk)}
        )
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
                "institute": str(self.institute_alpha.pk),
            },
            HTTP_ACCEPT_LANGUAGE="en",
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
                "institute": str(self.institute_alpha.pk),
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

    def test_unscoped_invoice_excludes_independently_billed_institutes(self):
        """Regression test: creating an unscoped ("all institutes") invoice for
        private + regular-institute lessons must NOT sweep in lessons from an
        institute with its own billing configuration (e.g. tiered pay or a
        tutor-no-show rule, like TutorSpace). Otherwise those lessons get marked
        paid and linked to the wrong invoice, and silently disappear from a later,
        dedicated invoice created for that institute.
        """
        tutorspace = Institute.objects.create(
            user=self.user,
            institute_name="TutorSpace",
            unpaid_on_tutor_no_show=True,
        )
        contract_tutorspace = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="TutorSpaceStudent",
            institute_fk=tutorspace,
            hourly_rate=Decimal("28.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        period_start = date(2025, 5, 1)
        period_end = date(2025, 5, 31)

        Lesson.objects.create(
            contract=self.contract_a,
            date=date(2025, 5, 5),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract_private,
            date=date(2025, 5, 6),
            start_time=time(11, 0),
            duration_minutes=60,
            status="taught",
        )
        tutorspace_lesson = Lesson.objects.create(
            contract=contract_tutorspace,
            date=date(2025, 5, 7),
            start_time=time(12, 0),
            duration_minutes=60,
            status="taught",
        )

        # Create the first invoice unscoped (no institute filter) - as done when
        # invoicing Abacus/private lessons together without singling out TutorSpace.
        InvoiceService.create_invoice_from_lessons(period_start, period_end, user=self.user)

        tutorspace_lesson.refresh_from_db()
        self.assertEqual(
            tutorspace_lesson.status,
            "taught",
            "TutorSpace lesson must remain billable, not be swept into the unscoped invoice.",
        )
        self.assertFalse(tutorspace_lesson.invoice_items.exists())

        # A dedicated invoice for TutorSpace must now find its lesson.
        tutorspace_invoice = InvoiceService.create_invoice_from_lessons(
            period_start, period_end, institute=tutorspace, user=self.user
        )
        self.assertEqual(tutorspace_invoice.items.count(), 1)
        self.assertEqual(tutorspace_invoice.items.first().lesson_id, tutorspace_lesson.pk)

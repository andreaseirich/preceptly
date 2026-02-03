"""
Tests for Invoice direct ownership (owner FK) and isolation.
"""

from datetime import date, time
from decimal import Decimal

from apps.billing.models import Invoice, InvoiceItem
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class InvoiceOwnershipIsolationTest(TestCase):
    """Two tutors: each sees only own invoices. Foreign invoice ID returns 404."""

    def setUp(self):
        self.tutor_a = User.objects.create_user(username="tutor_a", password="test")
        self.tutor_b = User.objects.create_user(username="tutor_b", password="test")

        self.student_a = Student.objects.create(
            user=self.tutor_a,
            first_name="A",
            last_name="Student",
        )
        self.student_b = Student.objects.create(
            user=self.tutor_b,
            first_name="B",
            last_name="Student",
        )
        self.contract_a = Contract.objects.create(
            student=self.student_a,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_b = Contract.objects.create(
            student=self.student_b,
            hourly_rate=Decimal("25"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
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
        self.invoice_a = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=self.contract_a, user=self.tutor_a
        )
        self.invoice_b = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=self.contract_b, user=self.tutor_b
        )

    def test_tutor_a_sees_only_own_invoices_in_list(self):
        self.client.login(username="tutor_a", password="test")
        response = self.client.get(reverse("billing:invoice_list"))
        self.assertEqual(response.status_code, 200)
        ids = [inv.pk for inv in response.context["invoices"]]
        self.assertIn(self.invoice_a.pk, ids)
        self.assertNotIn(self.invoice_b.pk, ids)

    def test_tutor_a_can_view_own_invoice_detail(self):
        self.client.login(username="tutor_a", password="test")
        response = self.client.get(
            reverse("billing:invoice_detail", kwargs={"pk": self.invoice_a.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_tutor_a_gets_404_for_foreign_invoice_detail(self):
        """404 (not 403) to avoid leaking existence."""
        self.client.login(username="tutor_a", password="test")
        response = self.client.get(
            reverse("billing:invoice_detail", kwargs={"pk": self.invoice_b.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_tutor_a_cannot_delete_foreign_invoice(self):
        self.client.login(username="tutor_a", password="test")
        response = self.client.post(
            reverse("billing:invoice_delete", kwargs={"pk": self.invoice_b.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Invoice.objects.filter(pk=self.invoice_b.pk).exists())

    def test_invoice_owner_set_on_create(self):
        self.assertEqual(self.invoice_a.owner_id, self.tutor_a.pk)
        self.assertEqual(self.invoice_b.owner_id, self.tutor_b.pk)


class InvoiceNumberUniqueConstraintTest(TestCase):
    """invoice_number unique per owner when not null."""

    def setUp(self):
        self.user1 = User.objects.create_user(username="u1", password="test")
        self.user2 = User.objects.create_user(username="u2", password="test")
        self.student1 = Student.objects.create(user=self.user1, first_name="A", last_name="B")
        self.student2 = Student.objects.create(user=self.user2, first_name="C", last_name="D")
        self.contract1 = Contract.objects.create(
            student=self.student1,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract2 = Contract.objects.create(
            student=self.student2,
            hourly_rate=Decimal("25"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_same_invoice_number_different_owners_allowed(self):
        Invoice.objects.create(
            owner=self.user1,
            payer_name="P1",
            contract=self.contract1,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            invoice_number="INV-0001",
        )
        Invoice.objects.create(
            owner=self.user2,
            payer_name="P2",
            contract=self.contract2,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            invoice_number="INV-0001",
        )
        self.assertEqual(Invoice.objects.filter(invoice_number="INV-0001").count(), 2)

    def test_null_invoice_number_multiple_allowed(self):
        Invoice.objects.create(
            owner=self.user1,
            payer_name="P1",
            contract=self.contract1,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            invoice_number=None,
        )
        Invoice.objects.create(
            owner=self.user1,
            payer_name="P2",
            contract=self.contract1,
            period_start=date(2025, 2, 1),
            period_end=date(2025, 2, 28),
            invoice_number=None,
        )
        self.assertEqual(
            Invoice.objects.filter(owner=self.user1, invoice_number__isnull=True).count(), 2
        )

    def test_duplicate_invoice_number_same_owner_raises_integrity_error(self):
        from django.db import IntegrityError

        Invoice.objects.create(
            owner=self.user1,
            payer_name="P1",
            contract=self.contract1,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            invoice_number="INV-001",
        )
        with self.assertRaises(IntegrityError):
            Invoice.objects.create(
                owner=self.user1,
                payer_name="P2",
                contract=self.contract1,
                period_start=date(2025, 2, 1),
                period_end=date(2025, 2, 28),
                invoice_number="INV-001",
            )


class OwnerResolverTest(TestCase):
    """Test resolve_invoice_owner helper (for backfill logic validation)."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.student = Student.objects.create(
            user=self.user,
            first_name="A",
            last_name="B",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

    def test_resolve_owner_from_contract(self):
        from apps.billing.owner_resolver import resolve_invoice_owner

        invoice = Invoice.objects.create(
            owner=self.user,
            payer_name="P",
            contract=self.contract,
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
        )
        self.assertEqual(resolve_invoice_owner(invoice), self.user)

    def test_resolve_owner_from_items_when_no_contract(self):
        from apps.billing.owner_resolver import resolve_invoice_owner

        invoice = Invoice.objects.create(
            owner=self.user,
            payer_name="P",
            contract=None,
            period_start=date(2025, 3, 1),
            period_end=date(2025, 3, 31),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            lesson=self.lesson,
            description="Lesson",
            date=self.lesson.date,
            duration_minutes=60,
            amount=Decimal("30.00"),
        )
        self.assertEqual(resolve_invoice_owner(invoice), self.user)

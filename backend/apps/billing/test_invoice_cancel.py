"""Storno ausgestellter Rechnungen und eigene Nummern für alle Tarife
(Prüfbericht 27.09.2026, F1 Teil 2 und F2)."""

import tempfile
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing.models import Invoice
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.core.finance_metrics import recognized_revenue
from apps.core.selectors import IncomeSelector
from apps.lessons.models import Lesson


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class InvoiceCancelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.contract = self._contract(self.user)
        self.lessons = [self._lesson(self.contract, date(2025, 3, day)) for day in (5, 12)]
        self.invoice = self._invoice(self.user, self.contract)
        self.client.force_login(self.user)

    def _contract(self, user):
        return Contract.objects.create(
            user=user,
            first_name="Test",
            last_name="Student",
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )

    def _lesson(self, contract, day):
        return Lesson.objects.create(
            contract=contract,
            date=day,
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

    def _invoice(self, user, contract):
        return InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=contract, user=user
        )

    def _url(self, name, invoice=None):
        return reverse(f"billing:{name}", kwargs={"pk": (invoice or self.invoice).pk})

    def _send(self):
        self.client.post(self._url("invoice_mark_sent"))

    def _pay(self):
        self.client.post(self._url("invoice_mark_paid"), {"paid_date": "2025-04-01"})

    def _cancel(self, invoice=None):
        return self.client.post(self._url("invoice_cancel", invoice))

    def test_free_plan_numbers_run_per_tutor(self):
        self.assertEqual(self.invoice.invoice_number, "INV-0001")
        self._lesson(self.contract, date(2025, 3, 19))
        self.assertEqual(self._invoice(self.user, self.contract).invoice_number, "INV-0002")
        other = User.objects.create_user(username="andere", password="test")
        other_contract = self._contract(other)
        self._lesson(other_contract, date(2025, 3, 5))
        self.assertEqual(self._invoice(other, other_contract).invoice_number, "INV-0001")

    def test_cancel_creates_a_counter_invoice(self):
        self._send()

        self._cancel()

        self.invoice.refresh_from_db()
        storno = self.invoice.cancellation
        self.assertEqual(self.invoice.status, "cancelled")
        self.assertEqual(storno.status, "cancelled")
        self.assertEqual(storno.invoice_number, "INV-0002")
        self.assertEqual(storno.total_amount, -self.invoice.total_amount)
        self.assertTrue(storno.invoice_pdf)
        for item in storno.items.all():
            self.assertLess(item.amount, 0)
            self.assertIsNone(item.lesson_id)

    def test_lessons_can_be_billed_again(self):
        self._send()
        self._cancel()

        corrected = self._invoice(self.user, self.contract)

        self.assertEqual(corrected.invoice_number, "INV-0003")
        self.assertEqual(
            sorted(corrected.items.values_list("lesson_id", flat=True)),
            sorted(lesson.pk for lesson in self.lessons),
        )
        totals = IncomeSelector._invoiced_totals(Lesson.objects.filter(contract=self.contract))
        self.assertEqual(totals[self.lessons[0].pk], Decimal("30.00"))

    def test_cancelling_a_paid_invoice_releases_the_lessons_and_the_revenue(self):
        self._send()
        self._pay()
        self.assertEqual(recognized_revenue(self.user, 2025, 3), Decimal("60.00"))

        self._cancel()

        self.assertEqual(
            set(Lesson.objects.filter(contract=self.contract).values_list("status", flat=True)),
            {"taught"},
        )
        self.assertEqual(recognized_revenue(self.user, 2025, 3), Decimal("0"))

    def test_only_issued_invoices_can_be_cancelled(self):
        self._cancel()  # Entwurf
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "draft")

        self._send()
        self._cancel()
        self._cancel()  # zweimal
        storno = Invoice.objects.get(cancels=self.invoice)
        self._cancel(storno)  # Stornorechnung selbst

        self.assertEqual(Invoice.objects.filter(owner=self.user).count(), 2)

    def test_cancelled_invoice_cannot_be_paid(self):
        self._send()
        self._cancel()

        self._pay()

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "cancelled")

    def test_foreign_invoice_gives_404(self):
        self._send()
        other = User.objects.create_user(username="fremd", password="test")
        self.client.force_login(other)

        self.assertEqual(self._cancel().status_code, 404)

    def test_detail_pages_point_to_each_other(self):
        self._send()
        self._cancel()
        storno = Invoice.objects.get(cancels=self.invoice)

        original_page = self.client.get(self._url("invoice_detail"))
        storno_page = self.client.get(self._url("invoice_detail", storno))

        self.assertContains(original_page, self._url("invoice_detail", storno))
        self.assertContains(storno_page, self._url("invoice_detail"))
        self.assertNotContains(storno_page, self._url("invoice_cancel", storno))
        self.assertNotContains(original_page, self._url("invoice_cancel"))

"""Ausgestellte Rechnungen bleiben, wie sie verschickt wurden (Prüfbericht 27.09.2026, F1)."""

import tempfile
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing.models import Invoice
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class IssuedInvoiceLockTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=contract,
            date=date(2025, 3, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        self.invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=contract, user=self.user
        )
        self.client.force_login(self.user)

    def _url(self, name):
        return reverse(f"billing:{name}", kwargs={"pk": self.invoice.pk})

    def _send(self):
        self.client.post(self._url("invoice_mark_sent"))
        self.invoice.refresh_from_db()

    def test_sending_freezes_the_pdf(self):
        self._send()
        self.assertEqual(self.invoice.status, "sent")
        self.assertTrue(self.invoice.invoice_pdf)
        sent_pdf = self.invoice.invoice_pdf.name

        self.client.post(self._url("invoice_pdf_generate"))

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice_pdf.name, sent_pdf)

    def test_recipient_of_an_issued_invoice_stays(self):
        self._send()
        old_name = self.invoice.payer_name

        self.client.post(self._url("invoice_update_payer"), {"payer_name": "Jemand anderes"})

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payer_name, old_name)

    def test_issued_invoice_cannot_be_deleted(self):
        self._send()

        response = self.client.get(self._url("invoice_delete"))
        self.assertRedirects(response, self._url("invoice_detail"), fetch_redirect_response=False)
        self.client.post(self._url("invoice_delete"))

        self.assertTrue(Invoice.objects.filter(pk=self.invoice.pk).exists())

    def test_payment_status_still_changes(self):
        self._send()

        self.client.post(self._url("invoice_mark_paid"), {"paid_date": "2025-04-01"})
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")

        self.client.post(self._url("invoice_undo_paid"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "sent")

    def test_detail_page_offers_no_changes_once_issued(self):
        self._send()

        response = self.client.get(self._url("invoice_detail"), HTTP_ACCEPT_LANGUAGE="de")

        self.assertNotContains(response, self._url("invoice_delete"))
        self.assertNotContains(response, 'id="payer-toggle-btn"')
        self.assertNotContains(response, self._url("invoice_pdf_generate"))
        self.assertContains(response, "ändern lässt sich nur noch der Zahlungsstatus")

    def test_drafts_stay_editable(self):
        self.client.post(self._url("invoice_update_payer"), {"payer_name": "Neuer Name"})
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payer_name, "Neuer Name")

        self.client.post(self._url("invoice_delete"))

        self.assertFalse(Invoice.objects.filter(pk=self.invoice.pk).exists())

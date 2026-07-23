from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.billing.models import Invoice, InvoiceItem
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.lessons.models import Lesson


class ProbeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")

    def _contract(self, institute=None, name="A"):
        return Contract.objects.create(
            user=self.user,
            first_name=name,
            last_name="X",
            hourly_rate=Decimal("60.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
            institute_fk=institute,
        )

    def _sess(self, contract, d, status="taught", no_show=False):
        return Lesson.objects.create(
            contract=contract,
            date=d,
            start_time=time(10, 0),
            duration_minutes=60,
            status=status,
            tutor_no_show=no_show,
        )

    def test_multi_contract_create_count(self):
        c1 = self._contract(name="c1")
        c2 = self._contract(name="c2")
        self._sess(c1, date(2025, 8, 10))
        self._sess(c1, date(2025, 8, 12))
        self._sess(c2, date(2025, 8, 11))
        inv = InvoiceService.create_invoice_from_lessons(
            date(2025, 8, 1), date(2025, 8, 31), user=self.user
        )
        print("MULTI-CONTRACT create items:", inv.items.count())
        self.assertEqual(inv.items.count(), 3)

    def test_adversarial_exclude(self):
        c = self._contract()
        billed = self._sess(c, date(2025, 8, 10), status="paid")
        Invoice_ = Invoice.objects.create(
            owner=self.user,
            payer_name="x",
            payer_address="",
            contract=c,
            period_start=date(2025, 8, 1),
            period_end=date(2025, 8, 31),
            status="draft",
        )
        InvoiceItem.objects.create(
            invoice=Invoice_,
            lesson=billed,
            description="d",
            date=billed.date,
            duration_minutes=60,
            amount=Decimal("1"),
        )
        unbilled = self._sess(c, date(2025, 8, 11), status="taught")
        # orphan item (lesson set null)
        InvoiceItem.objects.create(
            invoice=Invoice_,
            lesson=None,
            description="orphan",
            date=date(2025, 8, 5),
            duration_minutes=60,
            amount=Decimal("1"),
        )
        qs = InvoiceService.get_billable_lessons(
            date(2025, 8, 1), date(2025, 8, 31), user=self.user
        )
        ids = list(qs.values_list("id", flat=True))
        print("ADVERSARIAL billable ids:", ids, "expected:", [unbilled.id])
        self.assertEqual(ids, [unbilled.id])

    def test_taught_but_item_from_deleted_invoice(self):
        # session taught, no item -> billable
        c = self._contract()
        s = self._sess(c, date(2025, 8, 10), status="taught")
        qs = InvoiceService.get_billable_lessons(
            date(2025, 8, 1), date(2025, 8, 31), user=self.user
        )
        print("SINGLE taught billable:", qs.count())
        self.assertEqual(qs.count(), 1)
        self.assertIn(s, qs)

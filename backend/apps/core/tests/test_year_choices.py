"""Jahr-Auswahl: jedes Jahr nur einmal, neuestes zuerst.

Anlass 02.10.2026: In der Steuerübersicht stand „2026“ neunmal im Auswahlfeld,
einmal je Tag mit einer Zahlung (.dates() mit nachgestelltem .order_by())."""

from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import Invoice
from apps.core.models import Expense, UserProfile


def _paid(owner, year, month, day):
    return Invoice.objects.create(
        owner=owner,
        status="paid",
        paid_at=timezone.make_aware(datetime(year, month, day, 12, 0)),
        period_start=date(year, month, 1),
        period_end=date(year, month, 28),
        total_amount=Decimal("100.00"),
    )


class YearChoicesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_years", password="pass")
        UserProfile.objects.update_or_create(user=self.user, defaults={"subscription_tier": "pro"})
        self.client.force_login(self.user)
        # drei Zahltage in 2026 und zwei in 2025 - früher ergab das fünf Einträge
        for year, month, day in (
            (2026, 1, 5),
            (2026, 3, 9),
            (2026, 3, 20),
            (2025, 11, 2),
            (2025, 12, 1),
        ):
            _paid(self.user, year, month, day)

    def test_tax_year_lists_each_year_once_newest_first(self):
        response = self.client.get(reverse("core:tax_year"), {"year": 2026})

        self.assertEqual(response.context["available_years"], [2026, 2025])
        self.assertContains(response, '<option value="2026" selected>', count=1)
        self.assertContains(response, '<option value="2025" >', count=1)

    def test_euer_lists_each_year_once_newest_first(self):
        response = self.client.get(reverse("core:euer"), {"year": 2026})

        self.assertEqual(response.context["available_years"], [2026, 2025])

    def test_requested_year_without_payments_is_added_once(self):
        response = self.client.get(reverse("core:tax_year"), {"year": 2024})

        self.assertEqual(response.context["available_years"], [2026, 2025, 2024])

    def test_expense_list_lists_each_year_once(self):
        for day in ("2026-01-05", "2026-03-09", "2026-03-20", "2025-11-02"):
            Expense.objects.create(
                user=self.user,
                date=day,
                amount=Decimal("10.00"),
                category="office",
                description="Material",
                business_use_percent=100,
            )

        response = self.client.get(reverse("core:expense_list"))

        years = list(response.context["available_years"])
        self.assertEqual(years, sorted(set(years), reverse=True))
        self.assertEqual(years.count(2026), 1)
        self.assertEqual(years.count(2025), 1)

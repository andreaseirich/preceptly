"""Serien-Detailseite: stürzte seit 18.06.2026 bei jedem Aufruf ab."""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.recurring_models import RecurringSession


class RecurringDetailPageTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="pass")
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"subscription_tier": "starter"}
        )
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lea",
            last_name="Schmidt",
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
        )
        self.client.force_login(self.tutor)

    def _series(self, weeks):
        start = date.today() + timedelta(days=7)
        return RecurringSession.objects.create(
            contract=self.contract,
            start_date=start,
            end_date=start + timedelta(weeks=weeks),
            start_time=time(15, 0),
            duration_minutes=60,
            recurrence_type="weekly",
            **{start.strftime("%A").lower(): True},
            is_active=True,
        )

    def _detail(self, series):
        return self.client.get(
            reverse("lessons:recurring_detail", kwargs={"pk": series.pk}), HTTP_ACCEPT_LANGUAGE="de"
        )

    def test_short_series_shows_exact_count(self):
        response = self._detail(self._series(weeks=2))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>3</strong>", html=False)

    def test_long_series_shows_ten_plus(self):
        response = self._detail(self._series(weeks=20))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>10+</strong>", html=False)

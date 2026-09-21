"""
A recurring series keeps is_active=True after its end date has passed, so
everything user-facing has to check the date too. Reported by a parent:
the portal still showed a series that ran out on 31.07. as current, while
no lessons were being created for it any more.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contracts.models import Contract
from apps.lessons.recurring_models import RecurringSession
from apps.portal.models import ParentStudentLink, PortalUser


class RecurringSeriesHasEndedTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_rs", password="pass")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Chris",
            last_name="Beispiel",
            hourly_rate=Decimal("20.00"),
            start_date=date(2026, 1, 1),
        )

    def _series(self, **kwargs):
        defaults = {
            "contract": self.contract,
            "start_date": date(2026, 2, 18),
            "start_time": time(15, 0),
            "duration_minutes": 60,
            "tuesday": True,
        }
        return RecurringSession.objects.create(**{**defaults, **kwargs})

    def test_past_end_date_counts_as_ended(self):
        self.assertTrue(self._series(end_date=timezone.localdate() - timedelta(days=1)).has_ended)

    def test_future_end_date_is_still_running(self):
        self.assertFalse(self._series(end_date=timezone.localdate() + timedelta(days=1)).has_ended)

    def test_open_ended_series_is_still_running(self):
        self.assertFalse(self._series(end_date=None).has_ended)

    def test_open_ended_series_ends_with_the_contract(self):
        self.contract.end_date = timezone.localdate() - timedelta(days=1)
        self.contract.save(update_fields=["end_date"])
        series = self._series(end_date=None)
        series.refresh_from_db()
        self.assertTrue(series.has_ended)


class PortalRecurringManageEndedTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_rm", password="pass")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Chris",
            last_name="Beispiel",
            hourly_rate=Decimal("20.00"),
            start_date=date(2026, 1, 1),
        )
        parent = User.objects.create_user(username="parent_rm", password="pass")
        portal_user = PortalUser.objects.create(user=parent, role="parent", tutor=self.tutor)
        ParentStudentLink.objects.create(parent=portal_user, contract=self.contract, is_active=True)
        self.client = Client()
        session = self.client.session
        session["portal_user_id"] = portal_user.pk
        session.save()
        self.url = reverse("portal:recurring_manage", args=[self.contract.pk])

    def _series(self, end_date):
        return RecurringSession.objects.create(
            contract=self.contract,
            start_date=date(2026, 2, 18),
            end_date=end_date,
            start_time=time(15, 0),
            duration_minutes=60,
            tuesday=True,
        )

    def test_ended_series_is_not_listed_as_running(self):
        ended = self._series(timezone.localdate() - timedelta(days=7))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["series"]), [])
        self.assertEqual(list(response.context["ended_series"]), [ended])
        self.assertContains(response, "Aktuell läuft keine Serie.")
        self.assertContains(response, "Beendete Serien")
        # no way to "end" a series that already ended
        self.assertNotContains(response, "Serie beenden")

    def test_running_series_is_listed_as_before(self):
        running = self._series(timezone.localdate() + timedelta(days=30))

        response = self.client.get(self.url)

        self.assertEqual(list(response.context["series"]), [running])
        self.assertEqual(list(response.context["ended_series"]), [])
        self.assertContains(response, "Serie beenden")


class TutorRecurringListEndedTest(TestCase):
    def test_ended_series_is_not_shown_as_active(self):
        tutor = User.objects.create_user(username="tutor_tl", password="pass")
        contract = Contract.objects.create(
            user=tutor,
            first_name="Chris",
            last_name="Beispiel",
            hourly_rate=Decimal("20.00"),
            start_date=date(2026, 1, 1),
        )
        RecurringSession.objects.create(
            contract=contract,
            start_date=date(2026, 2, 18),
            end_date=date(2026, 7, 31),
            start_time=time(15, 0),
            duration_minutes=60,
            tuesday=True,
        )
        self.client.force_login(tutor)

        response = self.client.get(reverse("lessons:recurring_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "31.07.2026")

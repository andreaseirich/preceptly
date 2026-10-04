"""Serien, die Familien im Portal anlegen: nur freie Tage werden gebucht, belegte ausgelassen.

Anlass 04.10.2026 (Andreas): "Serientermine sollen nur für die Tage gebucht werden, die frei sind. Alle
Termine sollen gebucht werden, nur die Tage, die nicht frei sind, sollen ausgelassen werden." Bis dahin
legte eine Portal-Serie Stunden auch dort an, wo der Tutor schon einen Termin oder eine Blockzeit hatte."""

import datetime as dt
from decimal import Decimal

import django.utils.timezone as tz
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.availability import BLOCKED, LESSON, BusyCalendar
from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession
from apps.lessons.recurring_service import RecurringSessionService
from apps.portal.models import ParentStudentLink, PortalUser

User = get_user_model()


def _aware(day, hour, minute=0):
    return tz.make_aware(dt.datetime.combine(day, dt.time(hour, minute)))


class SeriesFixture(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="skip_tutor", password="pass")
        UserProfile.objects.update_or_create(user=self.tutor, defaults={"subscription_tier": "pro"})
        self.contract = self._contract(self.tutor, "Lea", "Schmidt")
        self.other = self._contract(self.tutor, "Anderer", "Schüler")
        account = PortalUser.objects.create(
            user=User.objects.create_user(username="skip_portal", password="pass"),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(parent=account, contract=self.contract, is_active=True)
        session = self.client.session
        session["portal_user_id"] = account.pk
        session.save()

        today = dt.date.today()
        self.monday = today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)
        self.mondays = [self.monday + dt.timedelta(weeks=n) for n in range(4)]

    @staticmethod
    def _contract(tutor, first, last):
        return Contract.objects.create(
            user=tutor,
            first_name=first,
            last_name=last,
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )

    def lesson(self, day, hour=16, minute=0, minutes=60, status="planned", contract=None):
        return Session.objects.create(
            contract=contract or self.other,
            date=day,
            start_time=dt.time(hour, minute),
            duration_minutes=minutes,
            status=status,
        )

    def series(self, **post):
        data = {
            "start_time": "16:00",
            "start_date": self.monday.isoformat(),
            "end_date": self.mondays[-1].isoformat(),
            "monday": "on",
        }
        data.update(post)
        return self.client.post(
            reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk}),
            data,
            follow=True,
        )

    def booked(self):
        return sorted(Session.objects.filter(contract=self.contract).values_list("date", flat=True))

    @staticmethod
    def shown(day):
        return day.strftime("%d.%m.%Y")


class PortalSeriesSkipBusyTest(SeriesFixture):
    def test_all_free_days_are_booked(self):
        response = self.series()

        self.assertEqual(self.booked(), self.mondays)
        self.assertContains(response, "4 Termine gebucht")
        self.assertNotContains(response, "ausgelassen")

    def test_a_day_with_another_lesson_is_left_out_and_the_rest_booked(self):
        busy = self.lesson(self.mondays[1])

        response = self.series()

        self.assertEqual(self.booked(), [self.mondays[0], *self.mondays[2:]])
        self.assertContains(response, "3 Termine gebucht")
        self.assertContains(response, "1 Tag war schon belegt und wurde ausgelassen")
        self.assertContains(response, self.shown(self.mondays[1]))
        self.assertTrue(Session.objects.filter(pk=busy.pk).exists())  # die fremde Stunde bleibt

    def test_partial_overlap_blocks_but_touching_lessons_do_not(self):
        self.lesson(self.mondays[0], 16, 30)  # 16:30-17:30 überschneidet 16:00-17:00
        self.lesson(self.mondays[1], 15, 0)  # 15:00-16:00 endet genau, wenn die Serie beginnt
        self.lesson(self.mondays[2], 17, 0)  # 17:00-18:00 beginnt genau, wenn die Serie endet

        self.series()

        self.assertEqual(self.booked(), self.mondays[1:])

    def test_blocked_time_and_multi_day_vacation_leave_days_out(self):
        BlockedTime.objects.create(
            user=self.tutor,
            title="Arzt",
            start_datetime=_aware(self.mondays[1], 15, 30),
            end_datetime=_aware(self.mondays[1], 16, 30),
        )
        BlockedTime.objects.create(
            user=self.tutor,
            title="Urlaub",
            start_datetime=_aware(self.mondays[3] - dt.timedelta(days=2), 18, 0),
            end_datetime=_aware(self.mondays[3] + dt.timedelta(days=2), 10, 0),
        )

        response = self.series()

        self.assertEqual(self.booked(), [self.mondays[0], self.mondays[2]])
        self.assertContains(response, "2 Tage waren schon belegt und wurden ausgelassen")

    def test_cancelled_lessons_and_other_tutors_do_not_block(self):
        self.lesson(self.mondays[0], status="cancelled")
        stranger = User.objects.create_user(username="skip_stranger", password="pass")
        self.lesson(self.mondays[1], contract=self._contract(stranger, "Fremd", "Schüler"))

        self.series()

        self.assertEqual(self.booked(), self.mondays)

    def test_taught_and_paid_lessons_block(self):
        self.lesson(self.mondays[0], status="taught")
        self.lesson(self.mondays[1], status="paid")

        self.series()

        self.assertEqual(self.booked(), self.mondays[2:])

    def test_when_every_day_is_busy_no_series_is_created(self):
        for day in self.mondays:
            self.lesson(day)

        response = self.series()

        self.assertEqual(self.booked(), [])
        self.assertFalse(RecurringSession.objects.filter(contract=self.contract).exists())
        self.assertContains(response, "Es wurde keine Serie angelegt")
        self.assertEqual(response.status_code, 200)  # zurück auf dem Formular

    def test_biweekly_series_leaves_busy_days_out(self):
        self.lesson(self.mondays[2])

        self.series(recurrence_type="biweekly")

        # alle zwei Wochen: Tag 0 und Tag 2 - Tag 2 ist belegt
        self.assertEqual(self.booked(), [self.mondays[0]])

    def test_series_created_once_stays_when_some_days_exist_already(self):
        # Eine Stunde dieses Schülers zur selben Zeit zählt als „gibt es schon“, nicht als belegt
        self.lesson(self.mondays[1], contract=self.contract)

        self.series()

        self.assertEqual(self.booked(), self.mondays)
        self.assertTrue(RecurringSession.objects.filter(contract=self.contract).exists())

    def test_form_explains_the_rule(self):
        page = self.client.get(
            reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk})
        )

        self.assertContains(page, "werden ausgelassen")


class SeriesServiceTest(SeriesFixture):
    def _series(self, kind="weekly", end=None):
        return RecurringSession.objects.create(
            contract=self.contract,
            start_date=self.monday,
            end_date=end or self.mondays[-1],
            start_time=dt.time(16, 0),
            duration_minutes=60,
            recurrence_type=kind,
            monday=True,
            is_active=True,
        )

    def test_without_skip_busy_everything_is_booked_as_before(self):
        # Tutor-Serien und alle anderen Aufrufer ändern sich nicht
        self.lesson(self.mondays[1])

        result = RecurringSessionService.generate_sessions(self._series(), check_conflicts=False)

        self.assertEqual(result["created"], 4)
        self.assertEqual(result["busy"], [])

    def test_dry_run_reports_busy_days_and_saves_nothing(self):
        self.lesson(self.mondays[1])

        result = RecurringSessionService.generate_sessions(
            self._series(), check_conflicts=False, dry_run=True, skip_busy=True
        )

        self.assertEqual([s.date for s in result["preview"]], [self.mondays[0], *self.mondays[2:]])
        self.assertEqual(result["busy"], [{"date": self.mondays[1], "reason": LESSON}])
        self.assertEqual(self.booked(), [])

    def test_reason_tells_lesson_from_blocked_time(self):
        self.lesson(self.mondays[0])
        BlockedTime.objects.create(
            user=self.tutor,
            title="Arzt",
            start_datetime=_aware(self.mondays[1], 16, 0),
            end_datetime=_aware(self.mondays[1], 17, 0),
        )

        result = RecurringSessionService.generate_sessions(
            self._series(), check_conflicts=False, dry_run=True, skip_busy=True
        )

        self.assertEqual(
            [(b["date"], b["reason"]) for b in result["busy"]],
            [(self.mondays[0], LESSON), (self.mondays[1], BLOCKED)],
        )

    def test_monthly_series_leaves_busy_days_out(self):
        end = self.monday + dt.timedelta(days=400)
        candidates = [
            s.date
            for s in RecurringSessionService.generate_sessions(
                self._series("monthly", end), check_conflicts=False, dry_run=True
            )["preview"]
        ]
        self.assertGreaterEqual(len(candidates), 2)
        self.lesson(candidates[1])

        result = RecurringSessionService.generate_sessions(
            self._series("monthly", end), check_conflicts=False, dry_run=True, skip_busy=True
        )

        self.assertEqual([s.date for s in result["preview"]], [candidates[0], *candidates[2:]])
        self.assertEqual([b["date"] for b in result["busy"]], [candidates[1]])

    def test_busy_times_are_loaded_in_two_queries_however_long_the_series(self):
        for day in self.mondays:
            self.lesson(day)
        BlockedTime.objects.create(
            user=self.tutor,
            title="Urlaub",
            start_datetime=_aware(self.monday, 8),
            end_datetime=_aware(self.monday + dt.timedelta(days=20), 8),
        )

        with CaptureQueriesContext(connection) as queries:
            calendar = BusyCalendar(self.tutor, self.monday, self.monday + dt.timedelta(days=700))
            for offset in range(700):
                calendar.reason(self.monday + dt.timedelta(days=offset), dt.time(16, 0), 60)

        self.assertEqual(len(queries), 2)
        self.assertEqual(
            calendar.reason(self.monday + dt.timedelta(days=5), dt.time(9, 0), 60), BLOCKED
        )

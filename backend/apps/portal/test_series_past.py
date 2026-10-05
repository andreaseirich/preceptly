"""Portal-Serien lassen Termine aus, die schon vorbei sind.

Auftrag von Andreas, 05.10.2026 ("Ja, gleiche die Serien an"): Einzelbuchung und Verschieben lehnen vergangene
Uhrzeiten von heute ab, Serien legten die erste Stunde dagegen noch in der Vergangenheit an (Uhrzeit heute schon
vorbei, oder Startdatum zurück). Wie in test_week_jump_and_past.py ist "jetzt" festgelegt, relativ zum echten Datum.
"""

import datetime as dt
from decimal import Decimal

from django.urls import reverse

from apps.contracts.models import Contract
from apps.lessons.availability import OFF_HOURS, PAST, BusyCalendar
from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession
from apps.lessons.recurring_service import RecurringSessionService
from apps.portal.test_week_jump_and_past import NowFixture

WEEKDAY_FIELDS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
NOW_HOUR = 15  # "jetzt" ist heute 15:00


class SeriesPastFixture(NowFixture):
    def setUp(self):
        super().setUp()
        self.later = [self.today + dt.timedelta(days=7 * n) for n in (1, 2)]
        self.other = Contract.objects.create(
            user=self.tutor,
            first_name="Anderer",
            last_name="Schüler",
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )

    def lesson(self, day, hour):
        """Eine Stunde eines anderen Schülers des Tutors."""
        return Session.objects.create(
            contract=self.other,
            date=day,
            start_time=dt.time(hour, 0),
            duration_minutes=60,
            status="planned",
        )

    def series(self, start=None, end=None, time="14:00"):
        """Wöchentlich am Wochentag von heute."""
        data = {
            "start_time": time,
            "start_date": (start or self.today).isoformat(),
            "end_date": (end or self.today + dt.timedelta(days=14)).isoformat(),
            WEEKDAY_FIELDS[self.today.weekday()]: "on",
        }
        return self.client.post(
            reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk}),
            data,
            follow=True,
        )

    def booked_days(self):
        return sorted(Session.objects.filter(contract=self.contract).values_list("date", flat=True))

    @staticmethod
    def shown(day):
        return day.strftime("%d.%m.%Y")


class PortalSeriesPastTest(SeriesPastFixture):
    def test_a_time_that_has_passed_today_is_left_out_and_the_rest_booked(self):
        with self.at(self.today, NOW_HOUR):
            response = self.series(time="14:00")

        self.assertEqual(self.booked_days(), self.later)
        self.assertContains(response, "2 Termine gebucht")
        self.assertContains(
            response, f"1 Termin war schon vorbei und wurde ausgelassen: {self.shown(self.today)}."
        )

    def test_a_later_time_today_is_booked_too(self):
        with self.at(self.today, NOW_HOUR):
            response = self.series(time="16:00")

        self.assertEqual(self.booked_days(), [self.today, *self.later])
        self.assertContains(response, "3 Termine gebucht")
        self.assertNotContains(response, "schon vorbei")

    def test_a_start_date_in_the_past_leaves_the_past_days_out(self):
        past = [self.today - dt.timedelta(days=14), self.today - dt.timedelta(days=7)]

        with self.at(self.today, NOW_HOUR):
            response = self.series(start=past[0], time="16:00")

        self.assertEqual(self.booked_days(), [self.today, *self.later])
        self.assertContains(response, "2 Termine waren schon vorbei und wurden ausgelassen")
        self.assertContains(response, self.shown(past[0]))

    def test_when_everything_is_past_no_series_is_created(self):
        with self.at(self.today, NOW_HOUR):
            response = self.series(end=self.today, time="14:00")

        self.assertEqual(self.booked_days(), [])
        self.assertFalse(RecurringSession.objects.filter(contract=self.contract).exists())
        self.assertContains(response, "Alle gewünschten Termine liegen schon in der Vergangenheit.")
        self.assertContains(response, "Es wurde keine Serie angelegt")
        self.assertContains(response, "Wähle ein späteres Startdatum oder eine spätere Uhrzeit")

    def test_past_and_busy_days_are_reported_separately(self):
        self.lesson(self.later[0], 14)  # anderer Schüler, 14:00 in einer Woche

        with self.at(self.today, NOW_HOUR):
            response = self.series(time="14:00")

        self.assertEqual(self.booked_days(), [self.later[1]])
        self.assertContains(response, "1 Tag war schon belegt und wurde ausgelassen")
        self.assertContains(response, "1 Termin war schon vorbei und wurde ausgelassen")

    def test_when_every_day_is_past_or_busy_the_message_names_both(self):
        self.lesson(self.later[0], 14)

        with self.at(self.today, NOW_HOUR):
            response = self.series(end=self.later[0], time="14:00")

        self.assertEqual(self.booked_days(), [])
        self.assertContains(response, "nicht frei oder der Termin liegt schon in der Vergangenheit")
        self.assertContains(response, "Es wurde keine Serie angelegt")

    def test_a_session_that_exists_already_is_not_reported_as_past(self):
        existing = Session.objects.create(
            contract=self.contract,
            date=self.today,
            start_time=dt.time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        with self.at(self.today, NOW_HOUR):
            self.series(time="14:00")

        self.assertEqual(self.booked_days(), [self.today, *self.later])
        self.assertTrue(Session.objects.filter(pk=existing.pk).exists())

    def test_the_form_and_the_faqs_mention_it(self):
        form = self.client.get(
            reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk})
        )
        faq = self.client.get(reverse("portal:faq"))

        self.assertContains(form, "Termine, die schon vorbei sind, werden ausgelassen")
        self.assertContains(faq, "Termine, die schon vorbei sind, lässt Preceptly ebenfalls aus")


class ServiceAndCalendarTest(SeriesPastFixture):
    def _series(self, time=dt.time(14, 0)):
        return RecurringSession.objects.create(
            contract=self.contract,
            start_date=self.today,
            end_date=self.today + dt.timedelta(days=14),
            start_time=time,
            duration_minutes=60,
            **{WEEKDAY_FIELDS[self.today.weekday()]: True},
            is_active=True,
        )

    def test_without_only_future_past_sessions_are_created_as_before(self):
        # Serien des Tutors und alle anderen Aufrufer ändern sich nicht
        with self.at(self.today, NOW_HOUR):
            result = RecurringSessionService.generate_sessions(
                self._series(), check_conflicts=False, skip_busy=True
            )

        self.assertEqual(result["created"], 3)
        self.assertEqual(result["busy"], [])

    def test_only_future_reports_the_past_day_with_its_reason(self):
        with self.at(self.today, NOW_HOUR):
            result = RecurringSessionService.generate_sessions(
                self._series(),
                check_conflicts=False,
                dry_run=True,
                skip_busy=True,
                only_future=True,
            )

        self.assertEqual(result["busy"], [{"date": self.today, "reason": PAST}])
        self.assertEqual([s.date for s in result["preview"]], self.later)

    def test_past_wins_over_off_hours_and_future_times_outside_the_hours_stay_off_hours(self):
        with self.at(self.today, NOW_HOUR):
            calendar = BusyCalendar(
                self.tutor,
                self.today,
                self.later[0],
                enforce_working_hours=True,
                enforce_future=True,
            )

            self.assertEqual(
                calendar.reason(self.today, dt.time(10, 0), 60), PAST
            )  # auch außerhalb
            self.assertEqual(calendar.reason(self.later[0], dt.time(10, 0), 60), OFF_HOURS)
            self.assertIsNone(calendar.reason(self.later[0], dt.time(16, 0), 60))

    def test_the_calendar_ignores_the_clock_unless_asked(self):
        with self.at(self.today, NOW_HOUR):
            calendar = BusyCalendar(self.tutor, self.today, self.today)

            self.assertIsNone(calendar.reason(self.today, dt.time(14, 0), 60))

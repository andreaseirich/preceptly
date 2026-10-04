"""Arbeitszeiten im Portal und Serien des Tutors nur an freien Tagen.

Auftrag von Andreas, 04.10.2026:
- Familien können im Portal nur innerhalb der Arbeitszeiten des Tutors buchen, nicht nur laut Liste der
  freien Zeiten, sondern auch beim Speichern (Buchung, Verschieben) und bei Serien (andere Tage werden
  ausgelassen).
- Serien, die der Tutor selbst anlegt, buchen nur die freien Tage; belegte werden ausgelassen.
"""

import datetime as dt
from decimal import Decimal

import django.utils.timezone as tz
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.availability import LESSON, OFF_HOURS, BusyCalendar, working_windows
from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession
from apps.portal.models import ParentStudentLink, PortalUser

User = get_user_model()

HOURS = {
    "monday": [{"start": "14:00", "end": "19:00"}],
    "tuesday": [{"start": "09:00", "end": "12:00"}, {"start": "15:00", "end": "18:00"}],
}


def _aware(day, hour, minute=0):
    return tz.make_aware(dt.datetime.combine(day, dt.time(hour, minute)))


class WorkingWindowsTest(SimpleTestCase):
    MONDAY = dt.date(2026, 10, 5)

    def test_windows_of_a_day(self):
        self.assertEqual(working_windows(HOURS, self.MONDAY), [(dt.time(14, 0), dt.time(19, 0))])
        self.assertEqual(
            working_windows(HOURS, self.MONDAY + dt.timedelta(days=1)),
            [(dt.time(9, 0), dt.time(12, 0)), (dt.time(15, 0), dt.time(18, 0))],
        )
        self.assertEqual(working_windows(HOURS, self.MONDAY + dt.timedelta(days=2)), [])

    def test_broken_entries_are_skipped(self):
        broken = {"monday": [{"start": "x"}, "kaputt", None, {"start": "10:00", "end": "11:00"}]}

        self.assertEqual(working_windows(broken, self.MONDAY), [(dt.time(10, 0), dt.time(11, 0))])

    def test_no_hours_at_all(self):
        self.assertEqual(working_windows({}, self.MONDAY), [])
        self.assertEqual(working_windows(None, self.MONDAY), [])
        self.assertEqual(working_windows("kaputt", self.MONDAY), [])


class HoursFixture(TestCase):
    hours = HOURS

    def setUp(self):
        self.tutor = User.objects.create_user(username="hours_tutor", password="pass")
        UserProfile.objects.update_or_create(
            user=self.tutor,
            defaults={"subscription_tier": "pro", "default_working_hours": self.hours},
        )
        self.contract = self._contract(self.tutor, "Lea", "Schmidt")
        self.other = self._contract(self.tutor, "Anderer", "Schüler")
        self.account = PortalUser.objects.create(
            user=User.objects.create_user(username="hours_portal", password="pass"),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(
            parent=self.account, contract=self.contract, is_active=True
        )

        today = dt.date.today()
        self.monday = today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)
        self.mondays = [self.monday + dt.timedelta(weeks=n) for n in range(4)]
        self.wednesday = self.monday + dt.timedelta(days=2)

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

    def as_portal(self):
        self.client.logout()
        session = self.client.session
        session["portal_user_id"] = self.account.pk
        session.save()

    def as_tutor(self):
        self.client.logout()
        self.client.force_login(self.tutor)

    def lesson(self, day, hour=16, minute=0, minutes=60, contract=None, status="planned"):
        return Session.objects.create(
            contract=contract or self.other,
            date=day,
            start_time=dt.time(hour, minute),
            duration_minutes=minutes,
            status=status,
        )

    def booked(self, contract=None):
        sessions = Session.objects.filter(contract=contract or self.contract)
        return sorted(sessions.values_list("date", flat=True))


class BusyCalendarWorkingHoursTest(HoursFixture):
    def reason(self, day, hour, minute=0, minutes=60, **kwargs):
        calendar = BusyCalendar(self.tutor, day, day, **kwargs)
        return calendar.reason(day, dt.time(hour, minute), minutes)

    def test_hours_are_not_checked_unless_asked_for(self):
        self.assertIsNone(self.reason(self.monday, 20))
        self.assertIsNone(self.reason(self.wednesday, 10))

    def test_inside_the_hours_is_free(self):
        self.assertIsNone(self.reason(self.monday, 14, enforce_working_hours=True))
        self.assertIsNone(self.reason(self.monday, 18, enforce_working_hours=True))  # endet 19:00

    def test_before_after_and_across_the_edge_are_off_hours(self):
        for hour, minute in [(13, 0), (13, 30), (18, 30), (19, 0), (20, 0)]:
            with self.subTest(zeit=f"{hour}:{minute:02d}"):
                self.assertEqual(
                    self.reason(self.monday, hour, minute, enforce_working_hours=True), OFF_HOURS
                )

    def test_a_day_without_hours_is_off_hours(self):
        self.assertEqual(self.reason(self.wednesday, 16, enforce_working_hours=True), OFF_HOURS)

    def test_a_lesson_cannot_span_two_windows(self):
        tuesday = self.monday + dt.timedelta(days=1)

        self.assertIsNone(self.reason(tuesday, 10, enforce_working_hours=True))
        self.assertIsNone(self.reason(tuesday, 15, enforce_working_hours=True))
        self.assertEqual(self.reason(tuesday, 11, 30, enforce_working_hours=True), OFF_HOURS)
        self.assertEqual(self.reason(tuesday, 12, 30, enforce_working_hours=True), OFF_HOURS)

    def test_off_hours_wins_over_busy_but_busy_inside_the_hours_still_counts(self):
        self.lesson(self.monday, 20)
        self.lesson(self.monday, 16)

        self.assertEqual(self.reason(self.monday, 20, enforce_working_hours=True), OFF_HOURS)
        self.assertEqual(self.reason(self.monday, 16, enforce_working_hours=True), LESSON)

    def test_without_any_hours_nothing_is_restricted(self):
        UserProfile.objects.filter(user=self.tutor).update(default_working_hours={})
        tutor = User.objects.get(pk=self.tutor.pk)

        calendar = BusyCalendar(tutor, self.monday, self.monday, enforce_working_hours=True)

        self.assertIsNone(calendar.reason(self.monday, dt.time(3, 0), 60))

    def test_still_three_queries_for_any_number_of_checks(self):
        tutor = User.objects.get(pk=self.tutor.pk)  # Profil noch nicht geladen

        with CaptureQueriesContext(connection) as queries:
            calendar = BusyCalendar(
                tutor, self.monday, self.monday + dt.timedelta(days=60), enforce_working_hours=True
            )
            for offset in range(60):
                calendar.reason(self.monday + dt.timedelta(days=offset), dt.time(16, 0), 60)

        self.assertEqual(len(queries), 3)


class PortalBookingWorkingHoursTest(HoursFixture):
    def setUp(self):
        super().setUp()
        self.as_portal()

    def book(self, day, start):
        return self.client.post(
            reverse("portal:book", kwargs={"student_pk": self.contract.pk}),
            {"date": day.isoformat(), "start_time": start},
        )

    def test_a_time_inside_the_hours_is_booked(self):
        self.book(self.monday, "15:00")

        self.assertEqual(self.booked(), [self.monday])

    def test_times_outside_the_hours_are_refused(self):
        for day, start in [
            (self.monday, "13:00"),
            (self.monday, "18:30"),  # endet 19:30
            (self.monday, "20:00"),
            (self.wednesday, "16:00"),  # Mittwoch ohne Arbeitszeit
        ]:
            with self.subTest(tag=day.strftime("%a"), zeit=start):
                response = self.book(day, start)

                self.assertContains(response, "außerhalb der Arbeitszeiten deines Tutors")
        self.assertEqual(self.booked(), [])

    def test_a_tutor_without_hours_is_not_restricted(self):
        UserProfile.objects.filter(user=self.tutor).update(default_working_hours={})

        self.book(self.wednesday, "07:00")

        self.assertEqual(self.booked(), [self.wednesday])

    def test_the_list_of_free_times_still_matches(self):
        response = self.client.get(
            reverse("portal:availability", kwargs={"student_pk": self.contract.pk}),
            {"date": self.monday.isoformat()},
        )

        slots = response.json()["slots"]
        self.assertEqual(slots[0], "14:00")
        self.assertEqual(slots[-1], "18:00")
        for start in (slots[0], slots[-1]):  # was die Liste anbietet, lässt sich auch buchen
            self.book(self.monday, start)
            Session.objects.filter(contract=self.contract).delete()

    def test_rescheduling_checks_the_hours_too(self):
        day = self.mondays[1]  # genug Vorlauf für das Verschieben
        lesson = self.lesson(day, 15, contract=self.contract)
        url = reverse("portal:session_reschedule", args=[lesson.pk])

        refused = self.client.post(url, {"date": day.isoformat(), "start_time": "20:00"})
        lesson.refresh_from_db()
        self.assertContains(refused, "außerhalb der Arbeitszeiten deines Tutors")
        self.assertEqual(lesson.start_time, dt.time(15, 0))

        self.client.post(url, {"date": day.isoformat(), "start_time": "17:00"})
        lesson.refresh_from_db()
        self.assertEqual(lesson.start_time, dt.time(17, 0))


class PortalSeriesWorkingHoursTest(HoursFixture):
    def setUp(self):
        super().setUp()
        self.as_portal()

    def series(self, start="16:00", **days):
        data = {
            "start_time": start,
            "start_date": self.monday.isoformat(),
            "end_date": self.mondays[-1].isoformat(),
            **dict.fromkeys(days, "on"),
        }
        return self.client.post(
            reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk}),
            data,
            follow=True,
        )

    def test_days_outside_the_hours_are_left_out_and_the_rest_is_booked(self):
        response = self.series(monday=True, wednesday=True)  # Mittwoch hat keine Arbeitszeit

        self.assertEqual(self.booked(), self.mondays)
        self.assertContains(response, "4 Termine gebucht")
        self.assertContains(
            response,
            "3 Tage liegen außerhalb der Arbeitszeiten deines Tutors und wurden ausgelassen",
        )
        self.assertNotContains(response, "schon belegt")

    def test_days_inside_the_hours_are_all_booked(self):
        response = self.series(monday=True, tuesday=True)  # Dienstag 16:00 liegt in 15-18 Uhr

        self.assertEqual(len(self.booked()), 4 + 3)  # vier Montage, drei Dienstage im Zeitraum
        self.assertNotContains(response, "ausgelassen")

    def test_a_single_day_uses_the_singular(self):
        response = self.client.post(
            reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk}),
            {
                "start_time": "16:00",
                "start_date": self.monday.isoformat(),
                "end_date": (self.monday + dt.timedelta(days=3)).isoformat(),
                "monday": "on",
                "wednesday": "on",
            },
            follow=True,
        )

        self.assertEqual(self.booked(), [self.monday])
        self.assertContains(
            response,
            "1 Tag liegt außerhalb der Arbeitszeiten deines Tutors und wurde ausgelassen",
        )

    def test_a_time_outside_the_hours_on_every_day_creates_no_series(self):
        response = self.series("20:00", monday=True, tuesday=True)

        self.assertEqual(self.booked(), [])
        self.assertFalse(RecurringSession.objects.filter(contract=self.contract).exists())
        self.assertContains(
            response, "liegt diese Uhrzeit außerhalb der Arbeitszeiten deines Tutors"
        )
        self.assertContains(response, "Es wurde keine Serie angelegt")

    def test_busy_and_off_hours_days_are_reported_separately(self):
        self.lesson(self.mondays[1])

        response = self.series(monday=True, wednesday=True)

        self.assertEqual(self.booked(), [self.mondays[0], *self.mondays[2:]])
        self.assertContains(response, "1 Tag war schon belegt und wurde ausgelassen")
        self.assertContains(
            response, "außerhalb der Arbeitszeiten deines Tutors und wurden ausgelassen"
        )

    def test_when_every_day_is_busy_or_off_hours_the_message_names_both(self):
        for day in self.mondays:
            self.lesson(day)

        response = self.series(monday=True, wednesday=True)

        self.assertEqual(self.booked(), [])
        self.assertContains(response, "schon belegt oder außerhalb seiner Arbeitszeiten")
        self.assertContains(response, "Es wurde keine Serie angelegt")

    def test_a_tutor_without_hours_gets_series_on_every_day_as_before(self):
        UserProfile.objects.filter(user=self.tutor).update(default_working_hours={})

        response = self.series("07:00", monday=True, wednesday=True)

        self.assertEqual(len(self.booked()), 4 + 3)
        self.assertNotContains(response, "Arbeitszeiten deines Tutors")

    def test_the_form_and_the_faq_mention_the_hours(self):
        form = self.client.get(
            reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk})
        )
        faq = self.client.get(reverse("portal:faq"))

        self.assertContains(form, "außerhalb seiner Arbeitszeiten liegt")
        self.assertContains(faq, "liegt die Uhrzeit außerhalb seiner Arbeitszeiten")
        self.assertContains(faq, "dann erscheinen darunter die freien Uhrzeiten zum Anklicken")


class TutorSeriesSkipBusyTest(HoursFixture):
    """Serien, die der Tutor selbst anlegt, buchen nur die freien Tage."""

    def setUp(self):
        super().setUp()
        self.as_tutor()

    def series_form(self, **extra):
        data = {
            "contract": self.contract.pk,
            "start_date": self.monday.isoformat(),
            "end_date": self.mondays[-1].isoformat(),
            "start_time": "16:00",
            "duration_minutes": 60,
            "travel_time_before_minutes": 0,
            "travel_time_after_minutes": 0,
            "recurrence_type": "weekly",
            "monday": "on",
            "is_active": "on",
            "notes": "",
        }
        data.update(extra)
        return data

    def create_series(self, **extra):
        return self.client.post(
            reverse("lessons:recurring_create"), self.series_form(**extra), follow=True
        )

    def test_busy_days_are_left_out_and_reported(self):
        self.lesson(self.mondays[1])

        response = self.create_series()

        self.assertEqual(self.booked(), [self.mondays[0], *self.mondays[2:]])
        self.assertContains(response, "1 Tag war schon belegt und wurde ausgelassen")
        self.assertContains(response, self.mondays[1].strftime("%d.%m.%Y"))
        self.assertEqual(Session.objects.filter(contract=self.other).count(), 1)  # bleibt

    def test_blocked_times_and_vacations_count_too(self):
        BlockedTime.objects.create(
            user=self.tutor,
            title="Arzt",
            start_datetime=_aware(self.mondays[0], 15, 30),
            end_datetime=_aware(self.mondays[0], 16, 30),
        )
        BlockedTime.objects.create(
            user=self.tutor,
            title="Urlaub",
            start_datetime=_aware(self.mondays[2] - dt.timedelta(days=1), 12),
            end_datetime=_aware(self.mondays[2] + dt.timedelta(days=1), 12),
        )

        response = self.create_series()

        self.assertEqual(self.booked(), [self.mondays[1], self.mondays[3]])
        self.assertContains(response, "2 Tage waren schon belegt und wurden ausgelassen")

    def test_the_tutor_is_not_held_to_the_working_hours(self):
        response = self.create_series(start_time="20:00")  # außerhalb der Arbeitszeiten

        self.assertEqual(self.booked(), self.mondays)
        self.assertNotContains(response, "ausgelassen")

    def test_a_series_with_every_day_busy_is_still_created(self):
        for day in self.mondays:
            self.lesson(day)

        response = self.create_series()

        self.assertEqual(self.booked(), [])
        self.assertTrue(RecurringSession.objects.filter(contract=self.contract).exists())
        self.assertContains(response, "4 Tage waren schon belegt und wurden ausgelassen")

    def test_the_gap_to_other_lessons_counts_as_busy(self):
        UserProfile.objects.filter(user=self.tutor).update(min_gap_minutes=30)
        self.lesson(self.mondays[1], 17, 15)  # 17:15 liegt nur 15 Min nach 17:00

        self.create_series()

        self.assertEqual(self.booked(), [self.mondays[0], *self.mondays[2:]])

    def test_the_repeat_option_of_the_lesson_form_leaves_busy_days_out(self):
        self.lesson(self.mondays[2])

        response = self.client.post(
            reverse("lessons:create"),
            {
                "contract": self.contract.pk,
                "date": self.monday.isoformat(),
                "start_time": "16:00",
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
                "notes": "",
                "is_recurring": "on",
                "recurrence_type": "weekly",
                "recurrence_end_date": self.mondays[-1].isoformat(),
                "recurrence_weekdays": ["0"],
            },
            follow=True,
        )

        self.assertEqual(self.booked(), [self.mondays[0], self.mondays[1], self.mondays[3]])
        self.assertContains(response, "1 Tag war schon belegt und wurde ausgelassen")

    def test_generating_again_fills_in_days_that_have_become_free(self):
        busy = self.lesson(self.mondays[1])
        self.create_series()
        series = RecurringSession.objects.get(contract=self.contract)
        self.assertEqual(len(self.booked()), 3)

        busy.delete()
        self.client.post(reverse("lessons:recurring_generate", args=[series.pk]), follow=True)

        self.assertEqual(self.booked(), self.mondays)

    def test_generating_reports_the_busy_days(self):
        self.create_series()
        series = RecurringSession.objects.get(contract=self.contract)
        Session.objects.filter(contract=self.contract, date=self.mondays[3]).delete()
        self.lesson(self.mondays[3])

        response = self.client.post(
            reverse("lessons:recurring_generate", args=[series.pk]), follow=True
        )

        self.assertContains(response, "1 Tag war schon belegt und wurde ausgelassen")
        self.assertEqual(len(self.booked()), 3)

    def test_editing_a_series_regenerates_only_free_days(self):
        self.create_series()
        series = RecurringSession.objects.get(contract=self.contract)
        self.lesson(self.mondays[2], 17, 0)  # ab 17:00, die Serie wird auf 16:30 verschoben

        response = self.client.post(
            reverse("lessons:recurring_update", args=[series.pk]),
            self.series_form(start_time="16:30"),
            follow=True,
        )

        self.assertEqual(self.booked(), [self.mondays[0], self.mondays[1], self.mondays[3]])
        self.assertContains(response, "1 Tag war schon belegt und wurde ausgelassen")

    def test_the_form_explains_the_rule(self):
        page = self.client.get(reverse("lessons:recurring_create"))

        self.assertContains(page, "werden ausgelassen")

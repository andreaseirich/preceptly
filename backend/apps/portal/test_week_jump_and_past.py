"""Buchungsseite: erste Woche mit freien Zeiten, und vergangene Uhrzeiten von heute.

Auftrag von Andreas, 05.10.2026:
- Öffnet die Seite ohne Wochenangabe und in der aktuellen Woche ist nichts mehr frei, zeigt sie die erste Woche mit
  freien Zeiten (Anlass: Am Sonntag war die aktuelle Woche leer, und die Mutter sah scheinbar keinen freien Termin).
- Uhrzeiten von heute, die schon vorbei sind, werden nicht angeboten und beim Buchen und Verschieben abgelehnt.

Die Tests legen "jetzt" fest (apps.lessons.availability.local_now), relativ zum echten Datum, damit sie zu jeder
Tageszeit gleich laufen."""

import datetime as dt
from decimal import Decimal
from unittest import mock

import django.utils.timezone as tz
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.availability import is_past
from apps.lessons.models import Session
from apps.portal.models import ParentStudentLink, PortalUser
from apps.portal.views import _first_free_day

User = get_user_model()

DAILY = {
    day: [{"start": "14:00", "end": "19:00"}]
    for day in (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    )
}
ALL_DAY_STARTS = ["14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00"]


class NowFixture(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="jump_tutor", password="pass")
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"subscription_tier": "pro", "default_working_hours": DAILY}
        )
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lea",
            last_name="Schmidt",
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )
        account = PortalUser.objects.create(
            user=User.objects.create_user(username="jump_portal", password="pass"),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(parent=account, contract=self.contract, is_active=True)
        session = self.client.session
        session["portal_user_id"] = account.pk
        session.save()

        self.today = dt.date.today()
        self.this_monday = self.today - dt.timedelta(days=self.today.weekday())
        self.this_sunday = self.this_monday + dt.timedelta(days=6)
        self.next_monday = self.this_monday + dt.timedelta(days=7)

    @staticmethod
    def at(day, hour, minute=0):
        """Patcht "jetzt" auf diesen Zeitpunkt."""
        return mock.patch(
            "apps.lessons.availability.local_now",
            return_value=dt.datetime.combine(day, dt.time(hour, minute)),
        )

    def block(self, first_day, last_day):
        BlockedTime.objects.create(
            user=self.tutor,
            title="Urlaub",
            start_datetime=tz.make_aware(dt.datetime.combine(first_day, dt.time.min)),
            end_datetime=tz.make_aware(dt.datetime.combine(last_day, dt.time(23, 59))),
        )

    def book_page(self, **params):
        return self.client.get(reverse("portal:book", args=[self.contract.pk]), params)

    def slots(self, day):
        response = self.client.get(
            reverse("portal:availability", kwargs={"student_pk": self.contract.pk}),
            {"date": day.isoformat()},
        )
        return response.json()["slots"]

    def book(self, day, start):
        return self.client.post(
            reverse("portal:book", kwargs={"student_pk": self.contract.pk}),
            {"date": day.isoformat(), "start_time": start},
        )

    def booked(self):
        return list(
            Session.objects.filter(contract=self.contract).values_list("date", "start_time")
        )


class IsPastTest(TestCase):
    NOW = dt.datetime(2026, 10, 7, 15, 0)

    def test_earlier_and_equal_times_are_past(self):
        day = self.NOW.date()

        self.assertTrue(is_past(day, dt.time(14, 0), self.NOW))
        self.assertTrue(is_past(day, dt.time(15, 0), self.NOW))  # beginnt genau jetzt
        self.assertFalse(is_past(day, dt.time(15, 1), self.NOW))

    def test_other_days(self):
        self.assertTrue(is_past(dt.date(2026, 10, 6), dt.time(23, 0), self.NOW))
        self.assertFalse(is_past(dt.date(2026, 10, 8), dt.time(0, 0), self.NOW))


class PastTimesTodayTest(NowFixture):
    def test_todays_past_times_are_not_offered(self):
        with self.at(self.today, 15, 0):
            slots = self.slots(self.today)

        self.assertEqual(slots, ["15:30", "16:00", "16:30", "17:00", "17:30", "18:00"])

    def test_other_days_are_not_affected(self):
        tomorrow = self.today + dt.timedelta(days=1)

        with self.at(self.today, 23, 0):
            self.assertEqual(self.slots(tomorrow), ALL_DAY_STARTS)

    def test_after_the_last_start_nothing_is_left_today(self):
        with self.at(self.today, 18, 30):
            self.assertEqual(self.slots(self.today), [])

    def test_the_day_button_counts_only_what_is_still_free(self):
        with self.at(self.today, 15, 0):
            response = self.book_page()

        entry = next(w for w in response.context["weekdays"] if w["date"] == self.today)
        self.assertEqual(entry["free_count"], 6)

    def test_booking_a_time_that_has_passed_is_refused(self):
        with self.at(self.today, 15, 0):
            earlier = self.book(self.today, "14:00")
            right_now = self.book(self.today, "15:00")

        self.assertContains(earlier, "Diese Uhrzeit ist heute schon vorbei.")
        self.assertContains(right_now, "Diese Uhrzeit ist heute schon vorbei.")
        self.assertEqual(self.booked(), [])

    def test_booking_a_later_time_today_works(self):
        with self.at(self.today, 15, 0):
            self.book(self.today, "16:00")

        self.assertEqual(self.booked(), [(self.today, dt.time(16, 0))])

    def test_rescheduling_to_a_time_that_has_passed_is_refused(self):
        lesson = Session.objects.create(
            contract=self.contract,
            date=self.today + dt.timedelta(days=7),
            start_time=dt.time(15, 0),
            duration_minutes=60,
            status="planned",
        )
        url = reverse("portal:session_reschedule", args=[lesson.pk])

        with self.at(self.today, 15, 0):
            refused = self.client.post(url, {"date": self.today.isoformat(), "start_time": "14:00"})
            lesson.refresh_from_db()
            self.assertContains(refused, "Diese Uhrzeit ist heute schon vorbei.")
            self.assertEqual(lesson.date, self.today + dt.timedelta(days=7))

            self.client.post(url, {"date": self.today.isoformat(), "start_time": "17:00"})
            lesson.refresh_from_db()
            self.assertEqual((lesson.date, lesson.start_time), (self.today, dt.time(17, 0)))


class FirstWeekWithFreeTimesTest(NowFixture):
    def test_an_empty_current_week_shows_the_first_week_with_free_times(self):
        with self.at(self.this_sunday, 20, 0):  # Sonntagabend: diese Woche ist durch
            response = self.book_page()

        self.assertEqual(response.context["week_start"], self.next_monday)
        self.assertTrue(response.context["week_jumped"])
        self.assertContains(response, "Diese Woche ist nichts mehr frei")
        self.assertContains(response, "erste Woche mit freien Zeiten")
        self.assertGreater(response.context["week_free_total"], 0)

    def test_a_current_week_with_free_times_stays(self):
        with self.at(self.this_monday, 10, 0):
            response = self.book_page()

        self.assertEqual(response.context["week_start"], self.this_monday)
        self.assertFalse(response.context["week_jumped"])
        self.assertNotContains(response, "erste Woche mit freien Zeiten")

    def test_it_skips_weeks_that_are_blocked_completely(self):
        self.block(self.next_monday, self.next_monday + dt.timedelta(days=6))

        with self.at(self.this_sunday, 20, 0):
            response = self.book_page()

        self.assertEqual(response.context["week_start"], self.next_monday + dt.timedelta(days=7))
        self.assertTrue(response.context["week_jumped"])

    def test_an_explicit_week_is_always_respected(self):
        with self.at(self.this_sunday, 20, 0):
            response = self.book_page(
                year=self.this_monday.year, month=self.this_monday.month, day=self.this_monday.day
            )

        self.assertEqual(response.context["week_start"], self.this_monday)
        self.assertFalse(response.context["week_jumped"])
        self.assertContains(response, "In dieser Woche ist nichts mehr frei")

    def test_nothing_free_anywhere_stays_on_the_current_week(self):
        UserProfile.objects.filter(user=self.tutor).update(default_working_hours={})

        with self.at(self.this_monday, 10, 0):
            response = self.book_page()

        self.assertEqual(response.context["week_start"], self.this_monday)
        self.assertFalse(response.context["week_jumped"])
        self.assertContains(response, "In dieser Woche ist nichts mehr frei")

    def test_nothing_free_within_twelve_weeks_stays_on_the_current_week(self):
        self.block(self.this_monday, self.this_monday + dt.timedelta(weeks=13))

        with self.at(self.this_monday, 10, 0):
            response = self.book_page()

        self.assertEqual(response.context["week_start"], self.this_monday)
        self.assertFalse(response.context["week_jumped"])

    def test_invalid_week_values_do_not_break_the_page(self):
        for params in (
            {"year": "2026", "month": "13", "day": "1"},
            {"year": "abc"},
            {"year": "99999", "month": "1", "day": "1"},
            {"month": "2", "day": "30"},
        ):
            with self.subTest(params=params):
                response = self.book_page(**params)

                self.assertEqual(response.status_code, 200)

    def test_rescheduling_jumps_too(self):
        lesson = Session.objects.create(
            contract=self.contract,
            date=self.next_monday + dt.timedelta(days=14),
            start_time=dt.time(15, 0),
            duration_minutes=60,
            status="planned",
        )

        with self.at(self.this_sunday, 20, 0):
            response = self.client.get(reverse("portal:session_reschedule", args=[lesson.pk]))

        self.assertEqual(response.context["week_start"], self.next_monday)
        self.assertTrue(response.context["week_jumped"])

    def test_finding_the_week_costs_only_the_calendar_queries(self):
        tutor = User.objects.get(pk=self.tutor.pk)
        contract = Contract.objects.select_related("user").get(pk=self.contract.pk)
        contract.user = tutor

        with self.at(self.this_sunday, 20, 0), CaptureQueriesContext(connection) as queries:
            first = _first_free_day(contract, self.this_sunday)

        self.assertEqual(first, self.next_monday)
        self.assertLessEqual(len(queries), 3)  # Stunden, Blockzeiten, Profil - nicht je Tag

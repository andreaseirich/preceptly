"""Tag-Auswahl im Portal (Termin buchen und verschieben).

Anlass 04.10.2026: Eine Mutter schrieb, sie sehe nur die belegten Termine und könne keinen Termin anklicken. Das
stündliche Raster zeichnete nur "Belegt" ein, die Tage waren unscheinbare Spaltenköpfe, und die Tabelle war
mindestens 640 px breit (am Handy seitliches Scrollen). Jetzt ist jeder Tag eine Schaltfläche mit der Zahl der
freien Zeiten, aus derselben Regel wie die Liste darunter.
"""

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
from apps.lessons.models import Session
from apps.portal.models import ParentStudentLink, PortalUser
from apps.portal.views import _build_week_calendar

User = get_user_model()

HOURS = {
    "monday": [{"start": "14:00", "end": "19:00"}],  # 14:00 bis 18:00: 9 Startzeiten à 60 Min
    "tuesday": [{"start": "14:00", "end": "15:00"}],  # genau eine
    "thursday": [{"start": "09:00", "end": "11:00"}],
}


class PickerFixture(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="picker_tutor", password="pass")
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"subscription_tier": "pro", "default_working_hours": HOURS}
        )
        self.contract = self._contract("Lea", "Schmidt")
        self.other = self._contract("Anderer", "Schüler")
        account = PortalUser.objects.create(
            user=User.objects.create_user(username="picker_portal", password="pass"),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(parent=account, contract=self.contract, is_active=True)
        session = self.client.session
        session["portal_user_id"] = account.pk
        session.save()

        today = dt.date.today()
        self.monday = today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)
        self.tuesday = self.monday + dt.timedelta(days=1)

    def _contract(self, first, last):
        return Contract.objects.create(
            user=self.tutor,
            first_name=first,
            last_name=last,
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )

    def page(self, day=None, name="portal:book", args=None, **extra):
        day = day or self.monday
        return self.client.get(
            reverse(name, args=args or [self.contract.pk]),
            {"year": day.year, "month": day.month, "day": day.day, **extra},
        )

    def lesson(self, day, hour, minute=0):
        return Session.objects.create(
            contract=self.other,
            date=day,
            start_time=dt.time(hour, minute),
            duration_minutes=60,
            status="planned",
        )

    def day_entry(self, response, day):
        return next(w for w in response.context["weekdays"] if w["date"] == day)


class DayButtonsTest(PickerFixture):
    def test_every_day_is_a_button_with_its_free_times(self):
        response = self.page()

        self.assertEqual(response.content.decode().count('type="button" class="week-day-pick'), 7)
        self.assertContains(response, f'data-date="{self.monday.isoformat()}"')
        self.assertContains(response, "9 freie Zeiten")
        self.assertContains(response, "1 freie Zeit<")  # Dienstag: Einzahl
        self.assertContains(response, "nichts frei")  # Mittwoch ohne Arbeitszeit

    def test_busy_times_reduce_the_count(self):
        self.lesson(self.monday, 16)  # 16:00-17:00 nimmt 15:30, 16:00 und 16:30 weg

        response = self.page()

        self.assertEqual(self.day_entry(response, self.monday)["free_count"], 6)
        self.assertContains(response, "6 freie Zeiten")

    def test_blocked_times_reduce_the_count_too(self):
        BlockedTime.objects.create(
            user=self.tutor,
            title="Arzt",
            start_datetime=tz.make_aware(dt.datetime.combine(self.monday, dt.time(14, 0))),
            end_datetime=tz.make_aware(dt.datetime.combine(self.monday, dt.time(19, 0))),
        )

        response = self.page()

        self.assertEqual(self.day_entry(response, self.monday)["free_count"], 0)

    def test_the_count_always_matches_the_list_below(self):
        self.lesson(self.monday, 16)
        response = self.page()

        for entry in response.context["weekdays"]:
            with self.subTest(tag=entry["date"].strftime("%a")):
                listed = self.client.get(
                    reverse("portal:availability", kwargs={"student_pk": self.contract.pk}),
                    {"date": entry["date"].isoformat()},
                ).json()["slots"]
                self.assertEqual(entry["free"], listed)

    def test_past_days_are_disabled_and_have_nothing_free(self):
        response = self.page(self.monday - dt.timedelta(days=21))

        self.assertEqual(response.context["week_free_total"], 0)
        self.assertNotContains(response, ">nichts frei<")
        self.assertContains(response, ">vorbei<", count=7)
        self.assertContains(response, " disabled>", count=7 + 1)  # 7 Tage und der Buchen-Knopf

    def test_a_week_without_any_free_time_says_so(self):
        normal = self.page()
        UserProfile.objects.filter(user=self.tutor).update(default_working_hours={})

        empty = self.page()

        self.assertNotContains(normal, "In dieser Woche ist nichts mehr frei")
        self.assertContains(empty, "In dieser Woche ist nichts mehr frei")
        self.assertContains(empty, "Wechsle mit „Nächste Woche“")

    def test_the_week_navigation_stays(self):
        response = self.page()

        self.assertContains(response, "← Vorige Woche")
        self.assertContains(response, "Nächste Woche →")
        self.assertContains(response, self.monday.strftime("%d.%m."))


class MarkupTest(PickerFixture):
    def test_the_old_wide_table_is_gone(self):
        response = self.page()

        self.assertNotContains(response, "min-width: 640px")
        self.assertNotContains(response, "Wochenübersicht zur Terminauswahl")
        self.assertNotContains(response, "<table")

    def test_buttons_are_accessible(self):
        response = self.page()

        html = response.content.decode()
        self.assertIn('type="button" class="week-day-pick', html)
        self.assertEqual(html.count('aria-pressed="false"'), 7)
        self.assertIn('role="list"', html)
        self.assertIn('aria-label="Tage der Woche"', html)
        self.assertNotIn("onclick=", html)  # CSP: keine Inline-Handler

    def test_the_stylesheet_is_loaded_and_exists(self):
        from pathlib import Path

        response = self.page()

        self.assertContains(response, "css/week-picker.css")
        css = Path(__file__).resolve().parents[1] / "core" / "static" / "css" / "week-picker.css"
        text = css.read_text(encoding="utf-8")
        self.assertIn(".week-day-pick", text)
        self.assertIn(":focus-visible", text)
        self.assertIn("@media (min-width: 760px)", text)

    def test_the_booking_page_explains_the_next_step(self):
        response = self.page()

        self.assertContains(response, "Tippe auf einen Tag")
        self.assertContains(response, "Wähle zuerst einen Tag und eine Uhrzeit")
        self.assertContains(response, 'aria-describedby="submit-hint"')


class ReschedulePageTest(PickerFixture):
    def setUp(self):
        super().setUp()
        self.session_obj = Session.objects.create(
            contract=self.contract,
            date=self.monday + dt.timedelta(days=7),
            start_time=dt.time(15, 0),
            duration_minutes=60,
            status="planned",
        )

    def test_reschedule_shows_the_same_day_buttons(self):
        response = self.page(name="portal:session_reschedule", args=[self.session_obj.pk])

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "9 freie Zeiten")
        self.assertContains(response, "css/week-picker.css")
        self.assertContains(response, "Tippe auf einen Tag")
        self.assertContains(response, 'aria-live="polite"')


class QueryCountTest(PickerFixture):
    def test_free_times_for_a_week_cost_only_the_calendar_queries(self):
        for day in range(7):
            self.lesson(self.monday + dt.timedelta(days=day), 15)

        user = User.objects.get(pk=self.tutor.pk)
        contract = Contract.objects.select_related("user").get(pk=self.contract.pk)
        contract.user = user
        with CaptureQueriesContext(connection) as without:
            _build_week_calendar(contract, self.monday.year, self.monday.month, self.monday.day)
        user = User.objects.get(pk=self.tutor.pk)
        contract.user = user
        with CaptureQueriesContext(connection) as with_free:
            _build_week_calendar(
                contract,
                self.monday.year,
                self.monday.month,
                self.monday.day,
                with_free_slots=True,
            )

        # nicht sieben Tage mal drei Abfragen, sondern höchstens drei dazu (Stunden, Blockzeiten, Profil)
        self.assertLessEqual(len(with_free) - len(without), 3)

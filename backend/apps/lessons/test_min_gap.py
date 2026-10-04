"""Mindestabstand zwischen Terminen (Einstellung des Tutors), auch zu Blockzeiten.

Auftrag von Andreas, 04.10.2026. Zwischen dem Ende eines Termins (samt Fahrzeit danach) und dem Beginn des
nächsten (samt Fahrzeit davor) liegen mindestens so viele Minuten, zwischen Stunde und Blockzeit ebenso.
Der Tutor bekommt bei eigenen Stunden eine Warnung, Familien im Portal können solche Zeiten nicht buchen."""

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
from apps.lessons.availability import BusyCalendar
from apps.lessons.conflict_service import SessionConflictService
from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession
from apps.lessons.recurring_service import RecurringSessionService
from apps.lessons.spacing import min_gap_minutes
from apps.portal.models import ParentStudentLink, PortalUser
from apps.portal.views import _get_available_slots

User = get_user_model()


def _aware(day, hour, minute=0):
    return tz.make_aware(dt.datetime.combine(day, dt.time(hour, minute)))


class GapFixture(TestCase):
    gap = 30

    def setUp(self):
        self.tutor = User.objects.create_user(username="gap_tutor", password="pass")
        self.profile, _ = UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"subscription_tier": "pro", "min_gap_minutes": self.gap}
        )
        self.student = self._contract("Lea")
        self.other = self._contract("Anderer")
        self.day = dt.date.today() + dt.timedelta(days=5)

    def _contract(self, first, before=0, after=0):
        return Contract.objects.create(
            user=self.tutor,
            first_name=first,
            last_name="Test",
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=60,
            start_date=dt.date(2025, 1, 1),
            is_active=True,
            default_travel_time_before_minutes=before,
            default_travel_time_after_minutes=after,
        )

    def lesson(
        self,
        hour,
        minute=0,
        minutes=60,
        contract=None,
        before=0,
        after=0,
        day=None,
        status="planned",
    ):
        return Session.objects.create(
            contract=contract or self.other,
            date=day or self.day,
            start_time=dt.time(hour, minute),
            duration_minutes=minutes,
            travel_time_before_minutes=before,
            travel_time_after_minutes=after,
            status=status,
        )

    def block(self, hour, minute, end_hour, end_minute, day=None):
        day = day or self.day
        return BlockedTime.objects.create(
            user=self.tutor,
            title="Arzt",
            start_datetime=_aware(day, hour, minute),
            end_datetime=_aware(day, end_hour, end_minute),
        )


class ConflictServiceGapTest(GapFixture):
    def conflicts(self, session):
        return SessionConflictService.check_conflicts(session)

    def test_a_lesson_closer_than_the_gap_is_a_too_close_conflict(self):
        self.lesson(15, 0)  # 15:00-16:00
        mine = self.lesson(16, 15, contract=self.student)  # 15 Minuten danach

        found = self.conflicts(mine)

        self.assertEqual([(c["type"], c.get("too_close")) for c in found], [("lesson", True)])
        self.assertEqual(found[0]["gap_minutes"], 15)
        self.assertIn("Nur 15 Min.", found[0]["message"])

    def test_exactly_the_gap_is_fine(self):
        self.lesson(15, 0)
        mine = self.lesson(16, 30, contract=self.student)

        self.assertEqual(self.conflicts(mine), [])

    def test_real_overlap_stays_an_overlap(self):
        self.lesson(15, 0)
        mine = self.lesson(15, 30, contract=self.student)

        found = self.conflicts(mine)

        self.assertEqual(len(found), 1)
        self.assertNotIn("too_close", found[0])

    def test_gap_counts_before_the_lesson_as_well(self):
        self.lesson(17, 0)
        mine = self.lesson(15, 45, contract=self.student)  # endet 16:45, 15 Minuten vor 17:00

        self.assertEqual([c.get("too_close") for c in self.conflicts(mine)], [True])

    def test_a_blocked_time_too_close_is_a_conflict_too(self):
        self.block(17, 0, 18, 0)
        before = self.lesson(16, 0, contract=self.student)  # endet 17:00 - grenzt an
        after_gap = self.lesson(14, 0, contract=self.student)  # endet 15:00 - 120 Min Abstand

        found = self.conflicts(before)

        self.assertEqual([(c["type"], c.get("too_close")) for c in found], [("blocked_time", True)])
        self.assertEqual(self.conflicts(after_gap), [])

    def test_travel_times_count_as_part_of_the_lesson(self):
        self.lesson(15, 0, after=20)  # belegt bis 16:20
        mine = self.lesson(17, 0, contract=self.student, before=15)  # beginnt 16:45: 25 Min Abstand

        found = self.conflicts(mine)

        self.assertEqual([c.get("too_close") for c in found], [True])
        self.assertEqual(found[0]["gap_minutes"], 25)

    def test_without_a_minimum_nothing_changes(self):
        self.profile.min_gap_minutes = 0
        self.profile.save()
        self.lesson(15, 0)
        mine = self.lesson(16, 5, contract=self.student)

        self.assertEqual(self.conflicts(mine), [])

    def test_bulk_check_matches_the_single_check(self):
        self.lesson(15, 0)
        self.block(18, 0, 19, 0)
        sessions = [
            self.lesson(16, 15, contract=self.student),
            self.lesson(17, 15, contract=self.student),
            self.lesson(12, 0, contract=self.student),
        ]

        bulk = SessionConflictService.check_conflicts_bulk(
            list(Session.objects.filter(pk__in=[s.pk for s in sessions]))
        )

        for session in sessions:
            with self.subTest(start=session.start_time):
                single = [(c["type"], c.get("too_close")) for c in self.conflicts(session)]
                self.assertEqual(
                    [(c["type"], c.get("too_close")) for c in bulk[session.pk]], single
                )

    def test_another_tutors_gap_does_not_apply(self):
        stranger = User.objects.create_user(username="gap_other", password="pass")
        UserProfile.objects.update_or_create(user=stranger, defaults={"min_gap_minutes": 120})
        self.assertEqual(min_gap_minutes(self.tutor), 30)
        self.assertEqual(min_gap_minutes(stranger), 120)

    def test_detail_page_names_the_reason(self):
        self.client.force_login(self.tutor)
        self.lesson(15, 0)
        mine = self.lesson(16, 15, contract=self.student)

        page = self.client.get(reverse("lessons:detail", args=[mine.pk]))

        self.assertContains(page, "Zu wenig Abstand zu anderer Stunde")
        self.assertNotContains(page, "Zeitüberschneidung mit anderer Stunde")


class BusyCalendarGapTest(GapFixture):
    def free(self, hour, minute=0, minutes=60, before=0, after=0, day=None):
        day = day or self.day
        return (
            BusyCalendar(self.tutor, day, day).reason(
                day, dt.time(hour, minute), minutes, before, after
            )
            is None
        )

    def test_gap_travel_and_touching(self):
        self.lesson(15, 0)  # 15:00-16:00

        self.assertFalse(self.free(16, 0))  # grenzt an: 0 Min Abstand
        self.assertFalse(self.free(16, 29))
        self.assertTrue(self.free(16, 30))
        self.assertFalse(self.free(13, 31))  # endet 14:31: 29 Min vor 15:00
        self.assertTrue(self.free(13, 30))
        self.assertFalse(self.free(16, 45, before=20))  # Fahrzeit vorher: Beginn 16:25

    def test_travel_time_of_existing_lessons_blocks_too(self):
        self.profile.min_gap_minutes = 0
        self.profile.save()
        self.lesson(15, 0, before=30, after=30)  # belegt 14:30-16:30

        self.assertFalse(self.free(16, 0))
        self.assertTrue(self.free(16, 30))
        self.assertFalse(self.free(13, 45))  # endet 14:45

    def test_blocked_time_needs_the_gap_as_well(self):
        self.block(17, 0, 18, 0)

        self.assertFalse(self.free(15, 45))  # endet 16:45: 15 Min vor der Blockzeit
        self.assertTrue(self.free(15, 30))
        self.assertFalse(self.free(18, 29))
        self.assertTrue(self.free(18, 30))

    def test_the_excluded_lesson_does_not_block_itself(self):
        mine = self.lesson(15, 0, contract=self.student)

        calendar = BusyCalendar(self.tutor, self.day, self.day, exclude_pk=mine.pk)

        self.assertIsNone(calendar.reason(self.day, dt.time(15, 30), 60))

    def test_loading_takes_three_queries_however_long_the_range(self):
        for week in range(4):
            self.lesson(15, 0, day=self.day + dt.timedelta(weeks=week))
        self.block(8, 0, 9, 0)

        tutor = User.objects.get(pk=self.tutor.pk)  # frisch geladen: Profil noch nicht im Speicher
        with CaptureQueriesContext(connection) as queries:
            calendar = BusyCalendar(tutor, self.day, self.day + dt.timedelta(days=500))
            for offset in range(500):
                calendar.reason(self.day + dt.timedelta(days=offset), dt.time(16, 0), 60)

        self.assertEqual(len(queries), 3)  # Stunden, Blockzeiten, Mindestabstand


class PortalGapTest(GapFixture):
    def setUp(self):
        super().setUp()
        self.profile.default_working_hours = {
            self.day.strftime("%A").lower(): [{"start": "08:00", "end": "20:00"}]
        }
        self.profile.save()
        self.far = self._contract("Weit", before=20, after=10)
        account = PortalUser.objects.create(
            user=User.objects.create_user(username="gap_portal", password="pass"),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(parent=account, contract=self.far, is_active=True)
        session = self.client.session
        session["portal_user_id"] = account.pk
        session.save()

    def slots(self, **kwargs):
        return _get_available_slots(self.tutor, self.day, **kwargs)

    def test_offered_slots_keep_the_gap_and_the_travel_time(self):
        self.lesson(12, 0, minutes=60)  # 12:00-13:00

        slots = self.slots(duration_minutes=60)
        with_travel = self.slots(duration_minutes=60, travel_before=20, travel_after=10)

        self.assertNotIn("13:00", slots)  # grenzt an
        self.assertNotIn("13:00", with_travel)
        self.assertIn("13:30", slots)  # genau 30 Min Abstand
        self.assertNotIn("13:30", with_travel)  # Fahrzeit vorher 20: nur 10 Min Abstand
        self.assertIn("14:00", with_travel)
        self.assertNotIn("11:30", slots)  # endet 12:30
        self.assertIn("10:30", slots)  # endet 11:30: 30 Min vor 12:00

    def test_availability_api_uses_the_students_travel_times(self):
        self.lesson(12, 0, minutes=60)

        response = self.client.get(
            reverse("portal:availability", kwargs={"student_pk": self.far.pk}),
            {"date": self.day.isoformat()},
        )

        slots = response.json()["slots"]
        self.assertIn("14:00", slots)
        self.assertNotIn("13:30", slots)

    def _book(self, hour, minute=0):
        return self.client.post(
            reverse("portal:book", kwargs={"student_pk": self.far.pk}),
            {"date": self.day.isoformat(), "start_time": f"{hour:02d}:{minute:02d}"},
        )

    def test_booking_too_close_is_refused_and_a_fitting_time_works(self):
        self.lesson(12, 0, minutes=60)

        refused = self._book(13, 30)
        self.assertEqual(Session.objects.filter(contract=self.far).count(), 0)
        self.assertContains(refused, "Zeitkonflikt")

        self._book(14, 0)
        booked = Session.objects.get(contract=self.far)
        self.assertEqual(booked.start_time, dt.time(14, 0))
        self.assertEqual(
            (booked.travel_time_before_minutes, booked.travel_time_after_minutes), (20, 10)
        )

    def test_booking_next_to_a_blocked_time_needs_the_gap(self):
        self.block(17, 0, 18, 0)

        refused = self._book(15, 30)  # endet 16:30, mit Fahrzeit 16:40: nur 20 Min

        self.assertEqual(Session.objects.filter(contract=self.far).count(), 0)
        self.assertContains(refused, "Blockzeit")

    def test_rescheduling_keeps_the_gap_and_checks_blocked_times_now(self):
        lesson = self.lesson(10, 0, contract=self.far, before=20, after=10)
        self.lesson(14, 0)  # 14:00-15:00
        self.block(17, 0, 18, 0)
        url = reverse("portal:session_reschedule", args=[lesson.pk])

        too_close = self.client.post(url, {"date": self.day.isoformat(), "start_time": "15:15"})
        blocked = self.client.post(url, {"date": self.day.isoformat(), "start_time": "16:30"})
        lesson.refresh_from_db()
        self.assertEqual(lesson.start_time, dt.time(10, 0))
        self.assertContains(too_close, "Zeitkonflikt")
        self.assertContains(blocked, "Blockzeit")

        self.client.post(
            url, {"date": self.day.isoformat(), "start_time": "10:30"}
        )  # sich selbst überlappen ist erlaubt
        lesson.refresh_from_db()
        self.assertEqual(lesson.start_time, dt.time(10, 30))

    def test_series_leave_out_days_that_are_too_close(self):
        self.profile.default_working_hours = {"monday": [{"start": "08:00", "end": "20:00"}]}
        self.profile.save()
        monday = self.day + dt.timedelta(days=(7 - self.day.weekday()) % 7 or 7)
        mondays = [monday + dt.timedelta(weeks=n) for n in range(3)]
        self.lesson(15, 0, day=mondays[1])  # 15:00-16:00; die Serie liegt 16:20-17:10 mit Fahrzeit

        self.client.post(
            reverse("portal:recurring_create", kwargs={"student_pk": self.far.pk}),
            {
                "start_time": "16:30",
                "start_date": monday.isoformat(),
                "end_date": mondays[-1].isoformat(),
                "monday": "on",
            },
        )

        booked = sorted(Session.objects.filter(contract=self.far).values_list("date", flat=True))
        self.assertEqual(
            booked, [mondays[0], mondays[2]]
        )  # 16:10 Beginn mit Fahrzeit: nur 10 Min Abstand


class SettingsGapTest(GapFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.tutor)
        self.url = reverse("core:settings")

    def test_card_shows_the_current_value(self):
        page = self.client.get(self.url)

        self.assertContains(page, "Mindestabstand zwischen Terminen")
        self.assertContains(page, 'name="min_gap_minutes"')
        self.assertContains(page, 'value="30"')

    def test_tutor_can_change_it(self):
        self.client.post(self.url, {"save_min_gap": "1", "min_gap_minutes": "45"})
        self.profile.refresh_from_db()

        self.assertEqual(self.profile.min_gap_minutes, 45)

    def test_zero_switches_it_off(self):
        self.client.post(self.url, {"save_min_gap": "1", "min_gap_minutes": "0"})
        self.profile.refresh_from_db()

        self.assertEqual(self.profile.min_gap_minutes, 0)

    def test_invalid_values_are_refused_and_the_old_value_stays(self):
        for bad in ("-5", "241", "abc", "1.5"):
            with self.subTest(wert=bad):
                self.client.post(self.url, {"save_min_gap": "1", "min_gap_minutes": bad})
                self.profile.refresh_from_db()
                self.assertEqual(self.profile.min_gap_minutes, 30)

    def test_the_other_settings_forms_leave_it_alone(self):
        self.client.post(self.url, {"save_portal": "1", "portal_buffer_hint_enabled": "on"})
        self.profile.refresh_from_db()

        self.assertEqual(self.profile.min_gap_minutes, 30)


class SeriesServiceGapTest(GapFixture):
    def test_series_template_travel_and_gap_decide(self):
        monday = self.day + dt.timedelta(days=(7 - self.day.weekday()) % 7 or 7)
        self.lesson(15, 0, day=monday)  # endet 16:00
        series = RecurringSession.objects.create(
            contract=self.student,
            start_date=monday,
            end_date=monday + dt.timedelta(days=7),
            start_time=dt.time(16, 40),
            duration_minutes=60,
            travel_time_before_minutes=15,  # beginnt 16:25: 25 Min Abstand zu 16:00
            recurrence_type="weekly",
            monday=True,
            is_active=True,
        )

        result = RecurringSessionService.generate_sessions(
            series, check_conflicts=False, dry_run=True, skip_busy=True
        )

        self.assertEqual([b["date"] for b in result["busy"]], [monday])
        self.assertEqual([s.date for s in result["preview"]], [monday + dt.timedelta(days=7)])

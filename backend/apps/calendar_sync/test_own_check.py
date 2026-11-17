"""Kontrolle der eigenen Termine in einer verbundenen Kalenderadresse (own_check.py und ihre Anzeige)."""

from datetime import datetime, time, timedelta
from datetime import timezone as tz
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.crypto import encrypt_password
from apps.calendar_sync.ics_sync import sync_source
from apps.calendar_sync.models import IcsCalendarSource
from apps.calendar_sync.own_check import MAX_DETAILS, check_own_lessons
from apps.calendar_sync.test_ics_import import event, ics
from apps.contracts.models import Contract
from apps.lessons.models import Lesson

UTC = tz.utc
BERLIN = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
URL = "https://calendar.google.com/calendar/ical/anna%40gmail.com/private-0123456789abcdef0123/basic.ics"
HEADER = "X-WR-TIMEZONE:Europe/Berlin"


def stamp(moment):
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def own_event(uid, start, end, summary="Nachhilfe"):
    return event(
        f"UID:{uid}", f"DTSTART:{stamp(start)}", f"DTEND:{stamp(end)}", f"SUMMARY:{summary}"
    )


def other_event(uid, start, end, summary="Arzt"):
    return own_event(uid, start, end, summary)


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class OwnCheckTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.now = NOW  # die Meldungstests unten rechnen mit der echten Uhrzeit, weil die Ansicht das auch tut
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.contract = self.make_contract(self.user)
        self.source = IcsCalendarSource.objects.create(
            user=self.user,
            name="Nachhilfe - Google",
            encrypted_url=encrypt_password(URL),
            url_hash=IcsCalendarSource.hash_url(URL),
            host="calendar.google.com",
        )

    def make_contract(self, user, first="Max"):
        return Contract.objects.create(
            user=user,
            first_name=first,
            last_name="Muster",
            hourly_rate=Decimal("20.00"),
            start_date=NOW.date(),
        )

    def lesson(
        self, days, contract=None, status="planned", at=time(14, 0), minutes=60, before=0, after=0
    ):
        return Lesson.objects.create(
            contract=contract or self.contract,
            date=self.now.astimezone(BERLIN).date() + timedelta(days=days),
            start_time=at,
            duration_minutes=minutes,
            status=status,
            travel_time_before_minutes=before,
            travel_time_after_minutes=after,
        )

    def times(self, lesson):
        start = datetime.combine(lesson.date, lesson.start_time, tzinfo=BERLIN)
        return start, start + timedelta(minutes=lesson.duration_minutes)

    def block(self, lesson):
        start, end = self.times(lesson)
        return start - timedelta(minutes=lesson.travel_time_before_minutes), end + timedelta(
            minutes=lesson.travel_time_after_minutes
        )

    def copy(self, lesson, prefix="preceptly-session", span=None):
        start, end = span or self.times(lesson)
        return own_event(f"{prefix}-{lesson.pk}@preceptly.de", start, end)

    def sync(self, *events):
        return sync_source(self.source, data=ics(*events, header=HEADER), now=self.now)


class OwnLessonsComparisonTest(OwnCheckTestCase):
    def test_matching_copies_are_counted_and_nothing_is_reported(self):
        lessons = [self.lesson(1), self.lesson(2), self.lesson(3)]

        result = self.sync(*[self.copy(lesson) for lesson in lessons])

        own = result["own"]
        self.assertEqual(
            (own["found"], own["ok"], own["changed"], own["gone"], own["missing"]), (3, 3, 0, 0, 0)
        )
        self.assertEqual(result["skipped"], 3)
        self.assertFalse(
            BlockedTime.objects.exists()
        )  # eigene Stunden werden weiterhin nie zu Blockzeiten

    def test_the_result_is_stored_with_the_source(self):
        lesson = self.lesson(1)

        self.sync(self.copy(lesson))

        self.source.refresh_from_db()
        self.assertEqual(self.source.last_sync_summary["own"]["ok"], 1)

    def test_a_copy_with_travel_times_matches_too(self):
        # So schreibt der iCloud-Abgleich: der Zeitblock mit Fahrzeiten.
        lesson = self.lesson(1, before=20, after=15)

        own = self.sync(self.copy(lesson, span=self.block(lesson)))["own"]

        self.assertEqual((own["ok"], own["changed"]), (1, 0))

    def test_a_copy_with_only_the_lesson_time_matches_too(self):
        # So schreibt der Abo-Link: nur die Unterrichtszeit, auch wenn Fahrzeiten eingetragen sind.
        lesson = self.lesson(1, before=20, after=15)

        own = self.sync(self.copy(lesson))["own"]

        self.assertEqual((own["ok"], own["changed"]), (1, 0))

    def test_the_other_url_forms_of_the_feeds_are_recognised(self):
        tutor_feed, portal_feed = self.lesson(1), self.lesson(2)

        own = self.sync(
            self.copy(tutor_feed, prefix="preceptly-tutor-session"),
            self.copy(portal_feed, prefix="preceptly-portal-session"),
        )["own"]

        self.assertEqual((own["ok"], own["gone"]), (2, 0))

    def test_a_different_time_is_reported_with_the_time_of_the_real_lesson(self):
        lesson = self.lesson(1, at=time(14, 0))
        start, _end = self.times(lesson)
        moved = (start + timedelta(hours=1), start + timedelta(hours=2))

        own = self.sync(self.copy(lesson, span=moved))["own"]

        self.assertEqual((own["ok"], own["changed"]), (0, 1))
        self.assertEqual(own["details"]["changed"][0]["label"], start.strftime("%d.%m. 14:00"))
        self.assertEqual(own["details"]["changed"][0]["lesson"], lesson.pk)

    def test_a_different_length_is_reported(self):
        lesson = self.lesson(1, minutes=60)
        start, _end = self.times(lesson)

        own = self.sync(self.copy(lesson, span=(start, start + timedelta(minutes=45))))["own"]

        self.assertEqual(own["changed"], 1)

    def test_a_deleted_lesson_is_reported_as_gone(self):
        gone = self.lesson(1)
        copy = self.copy(gone)
        start, _end = self.times(gone)
        gone.delete()

        own = self.sync(copy)["own"]

        self.assertEqual((own["found"], own["gone"], own["ok"]), (1, 1, 0))
        self.assertEqual(own["details"]["gone"][0]["label"], start.strftime("%d.%m. 14:00"))

    def test_a_cancelled_lesson_is_reported_as_gone(self):
        lesson = self.lesson(1, status="cancelled")

        own = self.sync(self.copy(lesson))["own"]

        self.assertEqual((own["gone"], own["ok"]), (1, 0))

    def test_a_lesson_of_another_tutor_is_gone_and_reveals_nothing(self):
        stranger = User.objects.create_user(username="stranger", password="pass")
        theirs = self.lesson(1, contract=self.make_contract(stranger, first="Geheim"))
        mine = self.lesson(2)

        own = self.sync(self.copy(theirs), self.copy(mine))["own"]

        self.assertEqual((own["ok"], own["gone"]), (1, 1))
        self.assertNotIn("lesson", own["details"]["gone"][0])  # keine Nummer der fremden Stunde
        self.assertNotIn("Geheim", str(own))

    def test_an_unrecognisable_own_id_is_gone(self):
        start = datetime.combine(NOW.date() + timedelta(days=2), time(10, 0), tzinfo=BERLIN)

        own = self.sync(own_event("irgendwas@preceptly.de", start, start + timedelta(hours=1)))[
            "own"
        ]

        self.assertEqual((own["found"], own["gone"]), (1, 1))

    def test_a_missing_upcoming_lesson_is_reported(self):
        in_calendar = self.lesson(1)
        missing = self.lesson(3, at=time(16, 30))
        start, _end = self.times(missing)

        own = self.sync(self.copy(in_calendar))["own"]

        self.assertEqual((own["ok"], own["missing"]), (1, 1))
        self.assertEqual(own["details"]["missing"][0]["label"], start.strftime("%d.%m. 16:30"))

    def test_nothing_is_missing_when_the_calendar_has_no_own_appointments(self):
        # Ein privater Kalender ist keine Kopie der Stunden: 3 Stunden sind dort nicht "fehlend".
        for days in (1, 2, 3):
            self.lesson(days)
        start = datetime.combine(NOW.date() + timedelta(days=1), time(9, 0), tzinfo=BERLIN)

        result = self.sync(other_event("privat@google.com", start, start + timedelta(hours=1)))

        self.assertNotIn("own", result)
        self.assertEqual(result["created"], 1)  # der private Termin wird wie bisher zur Blockzeit

    def test_the_check_itself_reports_nothing_missing_for_a_calendar_without_own_appointments(self):
        # Der Abgleich ruft die Kontrolle dann gar nicht erst auf; die Funktion muss es trotzdem allein richtig machen.
        for days in (1, 2):
            self.lesson(days)

        own = check_own_lessons(self.user, [], self.now, self.now + timedelta(days=180))

        self.assertEqual((own["found"], own["missing"]), (0, 0))

    def test_lessons_that_are_over_or_cancelled_are_not_reported_as_missing(self):
        in_calendar = self.lesson(1)
        self.lesson(-3, status="taught")  # vorbei: nicht erwartet
        self.lesson(2, status="cancelled")  # abgesagt: nicht erwartet
        self.lesson(0, at=time(8, 0))  # heute 8 Uhr, jetzt ist 13 Uhr: vorbei

        own = self.sync(self.copy(in_calendar))["own"]

        self.assertEqual(own["missing"], 0)

    def test_lessons_beyond_the_window_are_not_reported_as_missing(self):
        in_calendar = self.lesson(1)
        self.lesson(179)  # gerade noch im Zeitraum
        self.lesson(200)  # dahinter: für den Import unsichtbar

        own = self.sync(self.copy(in_calendar))["own"]

        self.assertEqual(own["missing"], 1)

    def test_other_tutors_lessons_are_never_missing_for_this_tutor(self):
        stranger = User.objects.create_user(username="stranger", password="pass")
        self.lesson(2, contract=self.make_contract(stranger))
        in_calendar = self.lesson(1)

        own = self.sync(self.copy(in_calendar))["own"]

        self.assertEqual(own["missing"], 0)

    def test_the_numbers_are_complete_but_the_listed_times_are_limited(self):
        lessons = [self.lesson(days) for days in range(1, MAX_DETAILS + 4)]
        copies = []
        for lesson in lessons:
            start, _end = self.times(lesson)
            copies.append(
                self.copy(lesson, span=(start + timedelta(hours=1), start + timedelta(hours=2)))
            )

        own = self.sync(*copies)["own"]

        self.assertEqual(own["changed"], len(lessons))
        self.assertEqual(len(own["details"]["changed"]), MAX_DETAILS)

    def test_a_second_run_gives_the_same_picture_and_creates_nothing(self):
        lesson = self.lesson(1)
        self.sync(self.copy(lesson))

        again = self.sync(self.copy(lesson))

        self.assertEqual(again["own"]["ok"], 1)
        self.assertEqual((again["created"], again["updated"], again["deleted"]), (0, 0, 0))

    def test_a_failing_check_never_breaks_the_import(self):
        start = datetime.combine(NOW.date() + timedelta(days=2), time(9, 0), tzinfo=BERLIN)
        lesson = self.lesson(1)

        with patch(
            "apps.calendar_sync.ics_sync.check_own_lessons", side_effect=RuntimeError("boom")
        ):
            with self.assertLogs("apps.calendar_sync.ics_sync", level="ERROR") as logs:
                result = self.sync(
                    self.copy(lesson),
                    other_event("privat@google.com", start, start + timedelta(hours=1)),
                )

        self.assertEqual(result["created"], 1)
        self.assertNotIn("own", result)
        self.assertNotIn("boom", "\n".join(logs.output))

    def test_an_own_appointment_in_the_past_week_is_compared_too(self):
        lesson = self.lesson(
            -2, status="taught"
        )  # die Kopie liegt noch im Kalender (z. B. Abo-Link)

        own = self.sync(self.copy(lesson))["own"]

        self.assertEqual((own["found"], own["ok"]), (1, 1))


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class OwnCheckDisplayTest(OwnCheckTestCase):
    def setUp(self):
        super().setUp()
        self.client.defaults["HTTP_ACCEPT_LANGUAGE"] = "en"
        self.client.login(username="tutor", password="pass")

    def own_summary(self, **own):
        base = {
            "found": 5,
            "ok": 5,
            "changed": 0,
            "gone": 0,
            "missing": 0,
            "details": {"changed": [], "gone": [], "missing": []},
        }
        self.source.last_sync_summary = {
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 5,
            "own": {**base, **own},
        }
        self.source.save()

    def page(self):
        return self.client.get(reverse("core:settings")).content.decode()

    def test_the_source_shows_how_many_own_lessons_were_found_and_match(self):
        self.own_summary()

        html = self.page()

        self.assertIn("Own Preceptly lessons in this calendar: 5", html)
        self.assertIn("5 match", html)
        self.assertNotIn("Different time than in Preceptly", html)

    def test_differences_are_listed_with_their_times(self):
        self.own_summary(
            ok=2,
            changed=1,
            gone=2,
            missing=1,
            details={
                "changed": [{"label": "20.11. 14:00", "lesson": 1}],
                "gone": [{"label": "21.11. 10:00"}, {"label": "22.11. 10:00"}],
                "missing": [{"label": "23.11. 16:30", "lesson": 2}],
            },
        )

        html = self.page()

        self.assertIn("Different time than in Preceptly: 1", html)
        self.assertIn("20.11. 14:00", html)
        self.assertIn("No longer in Preceptly (deleted or cancelled): 2", html)
        self.assertIn("21.11. 10:00, 22.11. 10:00", html)
        self.assertIn("Missing in this calendar: 1", html)
        self.assertIn("23.11. 16:30", html)
        self.assertIn("short differences are normal", html)

    def test_a_cut_off_list_ends_with_an_ellipsis(self):
        self.own_summary(
            ok=0,
            changed=12,
            details={
                "changed": [{"label": f"{day}.11. 14:00", "lesson": day} for day in range(1, 11)],
                "gone": [],
                "missing": [],
            },
        )

        html = self.page()

        self.assertIn("Different time than in Preceptly: 12", html)
        self.assertIn("10.11. 14:00, …", html)

    def test_a_source_without_own_appointments_shows_no_such_block(self):
        self.source.last_sync_summary = {"created": 1, "updated": 0, "deleted": 0, "skipped": 0}
        self.source.save()

        self.assertNotIn("Own Preceptly lessons in this calendar", self.page())

    def test_the_labels_are_shown_in_german_too(self):
        self.own_summary(
            ok=3,
            changed=1,
            details={
                "changed": [{"label": "20.11. 14:00", "lesson": 1}],
                "gone": [],
                "missing": [],
            },
        )

        html = self.client.get(reverse("core:settings"), HTTP_ACCEPT_LANGUAGE="de").content.decode()

        self.assertIn("Eigene Preceptly-Stunden in diesem Kalender: 5", html)
        self.assertIn("Andere Uhrzeit als in Preceptly: 1", html)


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class OwnCheckMessageTest(OwnCheckTestCase):
    def setUp(self):
        super().setUp()
        self.source.delete()
        self.now = timezone.now()
        self.client.defaults["HTTP_ACCEPT_LANGUAGE"] = "en"
        self.client.login(username="tutor", password="pass")

    def add(self, *events):
        with patch(
            "apps.calendar_sync.views_ics.fetch_ics", return_value=ics(*events, header=HEADER)
        ):
            return self.client.post(
                reverse("calendar_sync:ics_add"), {"ics_url": URL, "name": "Test"}
            )

    def texts(self, response):
        return [str(message) for message in get_messages(response.wsgi_request)]

    def test_connecting_a_copy_of_the_lessons_explains_why_nothing_was_imported(self):
        lessons = [self.lesson(1), self.lesson(2)]

        response = self.add(*[self.copy(lesson) for lesson in lessons])

        text = " ".join(self.texts(response))
        self.assertIn("0 appointments were imported as blocked times", text)
        self.assertIn(
            "2 appointments come from Preceptly itself and are not imported as blocked times", text
        )
        self.assertNotIn("Differences", text)

    def test_the_message_names_the_differences(self):
        good, moved = self.lesson(1), self.lesson(2)
        self.lesson(3)  # steht nicht im Kalender
        start, _end = self.times(moved)
        gone = self.lesson(4)
        copy_of_gone = self.copy(gone)
        gone.delete()

        response = self.add(
            self.copy(good),
            self.copy(moved, span=(start + timedelta(hours=1), start + timedelta(hours=2))),
            copy_of_gone,
        )

        text = " ".join(self.texts(response))
        self.assertIn("1 have a different time than in Preceptly", text)
        self.assertIn("1 no longer exist in Preceptly", text)
        self.assertIn("1 lessons are missing in this calendar", text)

    def test_a_calendar_without_own_appointments_gets_no_extra_message(self):
        start = datetime.combine(self.now.date() + timedelta(days=1), time(9, 0), tzinfo=BERLIN)

        response = self.add(other_event("privat@google.com", start, start + timedelta(hours=1)))

        self.assertNotIn("come from Preceptly itself", " ".join(self.texts(response)))

"""Ganztägige Termine, die in Google als "Verfügbar" markiert sind: Google setzt das bei neuen ganztägigen Terminen von selbst.

Ohne Einstellung blockieren sie nichts (richtig für Geburtstage und Erinnerungen, falsch für "Urlaub", den man nicht umgestellt
hat). Die Einstellung je Quelle erlaubt, sie trotzdem zu blockieren; die Quelle zeigt, wie viele wegen "Verfügbar" übersprungen
wurden.
"""

from datetime import datetime, timedelta
from datetime import timezone as tz
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.crypto import encrypt_password
from apps.calendar_sync.ics_import import parse_occurrences
from apps.calendar_sync.ics_sync import sync_source
from apps.calendar_sync.models import IcsCalendarSource
from apps.calendar_sync.test_ics_import import WINDOW, event, ics

UTC = tz.utc
URL = "https://calendar.google.com/calendar/ical/anna%40gmail.com/private-0123456789abcdef0123/basic.ics"
HEADER = "X-WR-TIMEZONE:Europe/Berlin"


def all_day(
    uid="f1", first="20261120", last_exclusive="20261121", summary="Urlaub", *, free=True, extra=()
):
    lines = [
        f"UID:{uid}",
        f"DTSTART;VALUE=DATE:{first}",
        f"DTEND;VALUE=DATE:{last_exclusive}",
        f"SUMMARY:{summary}",
    ]
    if free:
        lines.append("TRANSP:TRANSPARENT")
    return event(*lines, *extra)


def timed(uid="t1", summary="Termin", *, free=True):
    lines = [
        f"UID:{uid}",
        "DTSTART:20261120T100000Z",
        "DTEND:20261120T110000Z",
        f"SUMMARY:{summary}",
    ]
    if free:
        lines.append("TRANSP:TRANSPARENT")
    return event(*lines)


class ParseFreeAllDayTest(TestCase):
    def parse(self, *events, block=False):
        stats = {}
        items = parse_occurrences(
            ics(*events, header=HEADER), *WINDOW, block_free_all_day=block, stats=stats
        )
        return items, stats

    def test_by_default_a_free_all_day_event_blocks_nothing_and_is_counted(self):
        items, stats = self.parse(all_day())

        self.assertEqual(items, [])
        self.assertEqual(stats["free"], 1)

    def test_with_the_setting_it_blocks_the_whole_day_in_local_time(self):
        [item], stats = self.parse(all_day(), block=True)

        self.assertTrue(item.all_day)
        self.assertEqual(
            item.start, datetime(2026, 11, 19, 23, 0, tzinfo=UTC)
        )  # 20.11. 00:00 Berlin
        self.assertEqual(item.end, datetime(2026, 11, 20, 23, 0, tzinfo=UTC))  # bis 21.11. 00:00
        self.assertNotIn("free", stats)

    def test_a_free_event_with_a_time_is_always_skipped(self):
        items, stats = self.parse(timed(), block=True)

        self.assertEqual(items, [])
        self.assertEqual(stats["free"], 1)

    def test_a_cancelled_all_day_event_stays_skipped_with_the_setting(self):
        items, stats = self.parse(all_day(extra=["STATUS:CANCELLED"]), block=True)

        self.assertEqual(items, [])
        self.assertNotIn("free", stats)  # abgesagt ist nicht "verfügbar"

    def test_a_busy_all_day_event_is_unaffected_by_the_setting(self):
        for block in (False, True):
            with self.subTest(einstellung=block):
                items, stats = self.parse(all_day(free=False), block=block)
                self.assertEqual(len(items), 1)
                self.assertNotIn("free", stats)

    def test_a_weekly_free_all_day_series_blocks_every_day_with_the_setting(self):
        series = all_day(
            uid="w1",
            first="20261102",
            last_exclusive="20261103",
            extra=["RRULE:FREQ=WEEKLY;COUNT=3"],
        )

        items, _stats = self.parse(series, block=True)

        self.assertEqual(len(items), 3)

    def test_every_skipped_occurrence_is_counted(self):
        series = all_day(
            uid="w1",
            first="20261102",
            last_exclusive="20261103",
            extra=["RRULE:FREQ=WEEKLY;COUNT=3"],
        )

        _items, stats = self.parse(series, timed(), all_day(uid="b1", free=False))

        self.assertEqual(stats["free"], 4)  # drei Wochentage und ein Termin mit Uhrzeit

    def test_the_statistics_are_optional(self):
        items = parse_occurrences(ics(all_day(), header=HEADER), *WINDOW)

        self.assertEqual(items, [])


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SyncFreeAllDayTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.source = IcsCalendarSource.objects.create(
            user=self.user,
            name="Privat",
            encrypted_url=encrypt_password(URL),
            url_hash=IcsCalendarSource.hash_url(URL),
            host="calendar.google.com",
        )
        self.now = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)

    def sync(self, *events):
        return sync_source(self.source, data=ics(*events, header=HEADER), now=self.now)

    def set_setting(self, value):
        self.source.block_free_all_day = value
        self.source.save()

    def test_the_setting_is_off_by_default(self):
        self.assertFalse(self.source.block_free_all_day)

    def test_without_the_setting_nothing_is_imported_and_the_skipped_ones_are_counted(self):
        result = self.sync(
            all_day(),
            timed(),
            all_day(uid="b", first="20261125", last_exclusive="20261126", free=False),
        )

        self.assertEqual(result["created"], 1)  # nur der als "Beschäftigt" markierte
        self.assertEqual(result["free"], 2)
        self.source.refresh_from_db()
        self.assertEqual(self.source.last_sync_summary["free"], 2)

    def test_with_the_setting_the_free_all_day_event_becomes_a_blocked_time(self):
        self.set_setting(True)

        result = self.sync(all_day(), timed())

        self.assertEqual((result["created"], result["free"]), (1, 1))
        blocked = BlockedTime.objects.get()
        self.assertEqual(blocked.title, "Urlaub")
        self.assertEqual(blocked.end_datetime - blocked.start_datetime, timedelta(hours=24))

    def test_switching_the_setting_on_adds_the_blocked_time_at_the_next_sync(self):
        self.sync(all_day())
        self.assertFalse(BlockedTime.objects.exists())

        self.set_setting(True)
        result = self.sync(all_day())

        self.assertEqual(result["created"], 1)
        self.assertEqual(BlockedTime.objects.count(), 1)

    def test_switching_it_off_removes_the_blocked_time_again(self):
        self.set_setting(True)
        self.sync(all_day())
        self.assertEqual(BlockedTime.objects.count(), 1)

        self.set_setting(False)
        result = self.sync(all_day())

        self.assertEqual(result["deleted"], 1)
        self.assertFalse(BlockedTime.objects.exists())

    def test_a_manual_blocked_time_is_untouched_when_the_setting_changes(self):
        manual = BlockedTime.objects.create(
            user=self.user,
            title="Von Hand",
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
        )
        self.set_setting(True)
        self.sync(all_day())

        self.set_setting(False)
        self.sync(all_day())

        self.assertTrue(BlockedTime.objects.filter(pk=manual.pk).exists())

    def test_nothing_skipped_gives_a_zero(self):
        result = self.sync(all_day(free=False))

        self.assertEqual(result["free"], 0)


def future_feed(*, free=True):
    day = timezone.now() + timedelta(days=5)
    first, last = day.strftime("%Y%m%d"), (day + timedelta(days=1)).strftime("%Y%m%d")
    return ics(all_day(first=first, last_exclusive=last, free=free), header=HEADER)


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class AllDaySettingViewTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.client.defaults["HTTP_ACCEPT_LANGUAGE"] = "en"
        self.client.login(username="tutor", password="pass")
        self.source = self.make_source(self.user)

    def make_source(self, user, url=URL, **fields):
        return IcsCalendarSource.objects.create(
            user=user,
            name="Privat",
            encrypted_url=encrypt_password(url),
            url_hash=IcsCalendarSource.hash_url(url),
            host="calendar.google.com",
            **fields,
        )

    def post(self, source=None, **data):
        with patch("apps.calendar_sync.ics_sync.fetch_ics", return_value=future_feed()):
            return self.client.post(
                reverse("calendar_sync:ics_all_day", args=[(source or self.source).pk]), data
            )

    def texts(self, response):
        return " ".join(str(m) for m in get_messages(response.wsgi_request))

    def test_switching_it_on_saves_and_syncs_at_once(self):
        response = self.post(block_free_all_day="on")

        self.assertEqual(response.status_code, 302)
        self.source.refresh_from_db()
        self.assertTrue(self.source.block_free_all_day)
        self.assertEqual(BlockedTime.objects.filter(user=self.user).count(), 1)
        self.assertIn("Saved.", self.texts(response))
        self.assertIn("1 new", self.texts(response))

    def test_switching_it_off_removes_what_it_had_added(self):
        self.source.block_free_all_day = True
        self.source.save()
        self.post(block_free_all_day="on")
        self.assertEqual(BlockedTime.objects.count(), 1)

        response = self.post()  # Haken entfernt: das Feld fehlt in der Anfrage

        self.source.refresh_from_db()
        self.assertFalse(self.source.block_free_all_day)
        self.assertFalse(BlockedTime.objects.exists())
        self.assertIn("1 removed", self.texts(response))

    def test_it_changes_only_the_own_source(self):
        mine_two = self.make_source(self.user, url=URL.replace("0123", "7777"))
        theirs = self.make_source(self.other, url=URL.replace("0123", "8888"))

        self.post(block_free_all_day="on")

        for source in (mine_two, theirs):
            source.refresh_from_db()
            self.assertFalse(source.block_free_all_day)

    def test_another_tutors_source_cannot_be_changed(self):
        theirs = self.make_source(self.other, url=URL.replace("0123", "8888"))

        with patch("apps.calendar_sync.ics_sync.fetch_ics") as fetch:
            response = self.client.post(
                reverse("calendar_sync:ics_all_day", args=[theirs.pk]), {"block_free_all_day": "on"}
            )

        self.assertEqual(response.status_code, 404)
        fetch.assert_not_called()
        theirs.refresh_from_db()
        self.assertFalse(theirs.block_free_all_day)

    def test_login_is_required(self):
        self.client.logout()

        with patch("apps.calendar_sync.ics_sync.fetch_ics") as fetch:
            response = self.client.post(
                reverse("calendar_sync:ics_all_day", args=[self.source.pk]),
                {"block_free_all_day": "on"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
        fetch.assert_not_called()

    def test_only_post_is_allowed(self):
        self.assertEqual(
            self.client.get(
                reverse("calendar_sync:ics_all_day", args=[self.source.pk])
            ).status_code,
            405,
        )

    def test_a_failing_fetch_still_keeps_the_setting_and_says_so(self):
        from apps.calendar_sync.ics_import import IcsError

        with patch(
            "apps.calendar_sync.ics_sync.fetch_ics", side_effect=IcsError("fetch_failed", "x")
        ):
            response = self.client.post(
                reverse("calendar_sync:ics_all_day", args=[self.source.pk]),
                {"block_free_all_day": "on"},
            )

        self.source.refresh_from_db()
        self.assertTrue(self.source.block_free_all_day)
        self.assertIn("could not be retrieved", self.texts(response))
        self.assertNotIn("private-", self.texts(response))


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class AllDaySettingDisplayTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.client.defaults["HTTP_ACCEPT_LANGUAGE"] = "en"
        self.client.login(username="tutor", password="pass")
        self.source = IcsCalendarSource.objects.create(
            user=self.user,
            name="Privat",
            encrypted_url=encrypt_password(URL),
            url_hash=IcsCalendarSource.hash_url(URL),
            host="calendar.google.com",
        )

    def page(self, lang="en"):
        return self.client.get(reverse("core:settings"), HTTP_ACCEPT_LANGUAGE=lang).content.decode()

    def test_the_checkbox_is_shown_unchecked_by_default(self):
        html = self.page()

        self.assertIn('name="block_free_all_day"', html)
        self.assertIn("Block all-day events even if they are marked “Free”", html)
        self.assertNotRegex(html, r'name="block_free_all_day"\s+checked')

    def test_the_checkbox_is_checked_when_the_setting_is_on(self):
        self.source.block_free_all_day = True
        self.source.save()

        self.assertRegex(self.page(), r'name="block_free_all_day"\s+checked')

    def test_the_form_belongs_to_its_own_source(self):
        self.assertIn(reverse("calendar_sync:ics_all_day", args=[self.source.pk]), self.page())

    def test_the_number_of_skipped_free_events_is_shown(self):
        self.source.last_sync_summary = {
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "free": 3,
        }
        self.source.save()

        self.assertIn("Skipped because marked “Free”: 3", self.page())

    def test_nothing_is_shown_when_none_were_skipped(self):
        self.source.last_sync_summary = {
            "created": 1,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "free": 0,
        }
        self.source.save()

        self.assertNotIn("Skipped because marked", self.page())

    def test_the_texts_are_translated(self):
        self.source.last_sync_summary = {
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "free": 2,
        }
        self.source.save()

        html = self.page("de")

        self.assertIn(
            "Ganztägige Termine auch blockieren, wenn sie als „Verfügbar“ markiert sind", html
        )
        self.assertIn("Übersprungen, weil als „Verfügbar“ markiert: 2", html)

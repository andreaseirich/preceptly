"""Termine aus einer Kalenderadresse mit den Blockzeiten abgleichen (ics_sync.py)."""

from datetime import datetime, timedelta
from datetime import timezone as tz
from io import StringIO

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.crypto import encrypt_password
from apps.calendar_sync.ics_import import IcsError
from apps.calendar_sync.ics_sync import (
    ERROR_INTERVAL,
    MIN_INTERVAL,
    sync_all_ics_sources,
    sync_source,
)
from apps.calendar_sync.models import IcsCalendarSource, IcsEventMapping
from apps.calendar_sync.test_ics_import import event, ics

UTC = tz.utc
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
URL = "https://calendar.google.com/calendar/ical/anna%40gmail.com/private-0123456789abcdef0123/basic.ics"


def meeting(
    uid="m1@google.com", day="20261120", summary="Vorlesung", start="100000", end="113000", extra=()
):
    return event(
        f"UID:{uid}",
        f"DTSTART:{day}T{start}Z",
        f"DTEND:{day}T{end}Z",
        f"SUMMARY:{summary}",
        *extra,
    )


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SyncSourceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.source = self.make_source(self.user)

    def make_source(self, user, url=URL, name="Privat"):
        return IcsCalendarSource.objects.create(
            user=user,
            name=name,
            encrypted_url=encrypt_password(url),
            url_hash=IcsCalendarSource.hash_url(url),
            host="calendar.google.com",
        )

    def sync(self, *events, source=None, now=NOW, header="X-WR-TIMEZONE:Europe/Berlin"):
        source = source or self.source
        return sync_source(source, data=ics(*events, header=header), now=now)

    def test_new_appointments_become_blocked_times(self):
        result = self.sync(meeting())

        self.assertEqual((result["created"], result["updated"], result["deleted"]), (1, 0, 0))
        blocked = BlockedTime.objects.get(user=self.user)
        self.assertEqual(blocked.title, "Vorlesung")
        self.assertEqual(blocked.start_datetime, datetime(2026, 11, 20, 10, 0, tzinfo=UTC))
        self.assertEqual(blocked.end_datetime, datetime(2026, 11, 20, 11, 30, tzinfo=UTC))
        self.assertEqual(IcsEventMapping.objects.filter(source=self.source).count(), 1)

    def test_a_successful_run_is_recorded_on_the_source(self):
        self.source.last_sync_error = "fetch_failed"
        self.source.save()

        self.sync(meeting())

        self.source.refresh_from_db()
        self.assertEqual(self.source.last_synced_at, NOW)
        self.assertEqual(self.source.last_attempt_at, NOW)
        self.assertEqual(self.source.last_sync_error, "")
        self.assertEqual(self.source.last_sync_summary["created"], 1)

    def test_only_the_title_is_taken_over(self):
        self.sync(
            event(
                "UID:p1",
                "DTSTART:20261120T100000Z",
                "DTEND:20261120T110000Z",
                "SUMMARY:Arzt",
                "DESCRIPTION:Geheime Diagnose",
                "LOCATION:Praxis",
                "ATTENDEE:mailto:x@example.com",
            )
        )

        blocked = BlockedTime.objects.get()
        self.assertFalse(blocked.description)

    def test_a_second_run_with_the_same_data_changes_nothing(self):
        self.sync(meeting())
        pk = BlockedTime.objects.get().pk

        result = self.sync(meeting())

        self.assertEqual((result["created"], result["updated"], result["deleted"]), (0, 0, 0))
        self.assertEqual(BlockedTime.objects.get().pk, pk)

    def test_a_moved_appointment_replaces_its_blocked_time(self):
        self.sync(meeting())
        pk = BlockedTime.objects.get().pk

        result = self.sync(meeting(summary="Vorlesung verschoben", start="140000", end="153000"))

        # Der Beginn gehört zur Kennung: eine Verschiebung ist ein neuer Termin, der alte verschwindet.
        self.assertEqual((result["created"], result["deleted"]), (1, 1))
        self.assertFalse(BlockedTime.objects.filter(pk=pk).exists())
        self.assertEqual(BlockedTime.objects.get().title, "Vorlesung verschoben")

    def test_a_renamed_appointment_keeps_its_blocked_time(self):
        self.sync(meeting())
        pk = BlockedTime.objects.get().pk

        result = self.sync(meeting(summary="Neuer Titel"))

        self.assertEqual((result["created"], result["updated"], result["deleted"]), (0, 1, 0))
        blocked = BlockedTime.objects.get(pk=pk)
        self.assertEqual(blocked.title, "Neuer Titel")

    def test_an_appointment_that_disappears_from_the_calendar_is_removed(self):
        self.sync(meeting("a@g"), meeting("b@g", summary="Zweiter"))

        result = self.sync(meeting("a@g"))

        self.assertEqual(result["deleted"], 1)
        self.assertEqual([b.title for b in BlockedTime.objects.all()], ["Vorlesung"])
        self.assertEqual(IcsEventMapping.objects.count(), 1)

    def test_a_cancelled_appointment_is_removed(self):
        self.sync(meeting())

        result = self.sync(meeting(extra=["STATUS:CANCELLED"]))

        self.assertEqual(result["deleted"], 1)
        self.assertFalse(BlockedTime.objects.exists())

    def test_old_appointments_stay_when_they_leave_the_window(self):
        self.sync(meeting())

        later = NOW + timedelta(days=30)  # der Termin am 20.11. liegt jetzt vor dem Zeitraum
        result = self.sync(now=later)

        self.assertEqual(result["deleted"], 0)
        self.assertEqual(BlockedTime.objects.count(), 1)  # bleibt als Vergangenheit stehen
        self.assertFalse(IcsEventMapping.objects.exists())  # nur der Merkzettel wird aufgeräumt

    def test_a_blocked_time_the_tutor_deleted_is_not_created_again(self):
        self.sync(meeting())
        BlockedTime.objects.get().delete()

        result = self.sync(meeting())

        self.assertEqual(result["created"], 0)
        self.assertFalse(BlockedTime.objects.exists())
        mapping = IcsEventMapping.objects.get()
        self.assertIsNone(mapping.blocked_time_id)

    def test_the_reminder_goes_away_when_the_appointment_does(self):
        self.sync(meeting())
        BlockedTime.objects.get().delete()

        result = self.sync()

        self.assertEqual(result["deleted"], 0)  # es gab nichts mehr zu löschen
        self.assertFalse(IcsEventMapping.objects.exists())

    def test_a_deleted_appointment_that_changes_later_is_still_not_created_again(self):
        self.sync(meeting())
        BlockedTime.objects.get().delete()

        result = self.sync(meeting(summary="Neuer Titel"))  # darf weder abstürzen noch neu anlegen

        self.assertEqual((result["created"], result["updated"], result["deleted"]), (0, 0, 0))
        self.assertFalse(BlockedTime.objects.exists())

    def test_a_second_run_after_a_rename_changes_nothing(self):
        self.sync(meeting())
        self.sync(meeting(summary="Neuer Titel"))

        result = self.sync(meeting(summary="Neuer Titel"))

        self.assertEqual((result["created"], result["updated"], result["deleted"]), (0, 0, 0))

    def test_appointments_beyond_the_window_are_left_alone(self):
        far_day = (NOW + timedelta(days=170)).strftime("%Y%m%d")
        self.sync(meeting(day=far_day))

        # Die Uhr springt zurück: Der Termin liegt jetzt hinter dem Ende des Zeitraums und ist nicht zu sehen.
        result = self.sync(now=NOW - timedelta(days=30))

        self.assertEqual(result["deleted"], 0)
        self.assertEqual(BlockedTime.objects.count(), 1)
        self.assertEqual(IcsEventMapping.objects.count(), 1)

    def test_the_tutors_own_lessons_are_never_imported(self):
        result = self.sync(
            meeting("preceptly-tutor-session-7@preceptly.de", summary="Nachhilfe"),
            meeting("ok@g", summary="Echt"),
        )

        self.assertEqual((result["created"], result["skipped"]), (1, 1))
        self.assertEqual([b.title for b in BlockedTime.objects.all()], ["Echt"])

    def test_free_and_cancelled_appointments_are_not_imported(self):
        self.sync(
            meeting("t@g", summary="Frei", extra=["TRANSP:TRANSPARENT"]),
            meeting("c@g", summary="Abgesagt", extra=["STATUS:CANCELLED"]),
        )

        self.assertFalse(BlockedTime.objects.exists())

    def test_other_tutors_blocked_times_are_untouched(self):
        other = User.objects.create_user(username="other", password="pass")
        mine = BlockedTime.objects.create(
            user=other, title="Fremd", start_datetime=NOW, end_datetime=NOW + timedelta(hours=1)
        )

        self.sync(meeting())
        self.sync()

        self.assertTrue(BlockedTime.objects.filter(pk=mine.pk).exists())
        self.assertEqual(BlockedTime.objects.filter(user=other).count(), 1)

    def test_manual_blocked_times_are_untouched(self):
        manual = BlockedTime.objects.create(
            user=self.user, title="Urlaub", start_datetime=NOW, end_datetime=NOW + timedelta(days=3)
        )

        self.sync(meeting())
        self.sync()

        self.assertTrue(BlockedTime.objects.filter(pk=manual.pk).exists())

    def test_two_sources_do_not_touch_each_others_blocked_times(self):
        second = self.make_source(self.user, URL.replace("0123", "9999"), name="Zweiter")

        self.sync(meeting("a@g", summary="Aus Quelle 1"))
        self.sync(meeting("b@g", summary="Aus Quelle 2"), source=second)
        self.sync(meeting("a@g", summary="Aus Quelle 1"))  # Quelle 1 gleich, Quelle 2 unberührt

        self.assertEqual(
            sorted(b.title for b in BlockedTime.objects.all()), ["Aus Quelle 1", "Aus Quelle 2"]
        )

    def test_weekly_series_become_one_blocked_time_per_day(self):
        result = self.sync(
            event(
                "UID:w@g",
                "DTSTART:20261117T170000Z",
                "DTEND:20261117T180000Z",
                "RRULE:FREQ=WEEKLY;COUNT=3",
                "SUMMARY:Chor",
            )
        )

        self.assertEqual(result["created"], 3)
        self.assertEqual(BlockedTime.objects.count(), 3)


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SyncSourceErrorsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.source = IcsCalendarSource.objects.create(
            user=self.user,
            name="Privat",
            encrypted_url=encrypt_password(URL),
            url_hash=IcsCalendarSource.hash_url(URL),
            host="calendar.google.com",
        )

    def test_a_failed_fetch_is_recorded_without_the_address(self):
        def fetch(url):
            raise IcsError("fetch_failed", "The calendar server could not be reached.")

        result = sync_source(self.source, now=NOW, fetch=fetch)

        self.assertEqual(result["error"], "fetch_failed")
        self.source.refresh_from_db()
        self.assertEqual(self.source.last_sync_error, "fetch_failed")
        self.assertEqual(self.source.last_attempt_at, NOW)
        self.assertIsNone(self.source.last_synced_at)
        self.assertNotIn("private-0123", str(self.source.last_sync_summary))

    def test_the_decrypted_address_is_what_gets_fetched(self):
        seen = []

        def fetch(url):
            seen.append(url)
            return ics()

        sync_source(self.source, now=NOW, fetch=fetch)

        self.assertEqual(seen, [URL])

    def test_a_failed_run_keeps_the_blocked_times_from_the_last_good_run(self):
        sync_source(self.source, data=ics(meeting(), header="X-WR-TIMEZONE:Europe/Berlin"), now=NOW)

        sync_source(self.source, data=b"<html>Anmelden</html>", now=NOW + timedelta(minutes=20))

        self.assertEqual(BlockedTime.objects.count(), 1)
        self.source.refresh_from_db()
        self.assertEqual(self.source.last_sync_error, "not_ical")
        self.assertEqual(self.source.last_synced_at, NOW)  # der letzte gute Lauf bleibt sichtbar

    def test_the_error_is_cleared_by_the_next_good_run(self):
        sync_source(self.source, data=b"nonsense", now=NOW)

        sync_source(self.source, data=ics(), now=NOW + timedelta(hours=2))

        self.source.refresh_from_db()
        self.assertEqual(self.source.last_sync_error, "")

    def test_an_address_that_cannot_be_decrypted_is_reported(self):
        with override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            result = sync_source(self.source, now=NOW, fetch=lambda url: ics())

        self.assertEqual(result["error"], "credential")
        self.source.refresh_from_db()
        self.assertEqual(self.source.last_sync_error, "credential")


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SyncAllSourcesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.calls = []

    def make_source(self, user=None, suffix="1", **fields):
        url = URL.replace("0123", f"{suffix:0>4}")
        return IcsCalendarSource.objects.create(
            user=user or self.user,
            name=f"Quelle {suffix}",
            encrypted_url=encrypt_password(url),
            url_hash=IcsCalendarSource.hash_url(url),
            host="calendar.google.com",
            **fields,
        )

    def fetch(self, url):
        self.calls.append(url)
        return ics(meeting(uid=f"u{len(self.calls)}@g"), header="X-WR-TIMEZONE:Europe/Berlin")

    def test_a_new_source_is_synced(self):
        self.make_source()

        totals = sync_all_ics_sources(now=NOW, fetch=self.fetch)

        self.assertEqual((totals["sources"], totals["created"], totals["errors"]), (1, 1, 0))

    def test_a_source_that_was_just_synced_is_not_due(self):
        self.make_source(last_attempt_at=NOW - timedelta(minutes=5))

        totals = sync_all_ics_sources(now=NOW, fetch=self.fetch)

        self.assertEqual(totals["sources"], 0)
        self.assertEqual(self.calls, [])

    def test_a_source_is_due_after_the_interval(self):
        self.make_source(last_attempt_at=NOW - MIN_INTERVAL)

        self.assertEqual(sync_all_ics_sources(now=NOW, fetch=self.fetch)["sources"], 1)

    def test_the_five_minute_cron_does_not_push_the_interval_to_twenty_minutes(self):
        self.make_source(last_attempt_at=NOW - MIN_INTERVAL + timedelta(seconds=30))

        self.assertEqual(sync_all_ics_sources(now=NOW, fetch=self.fetch)["sources"], 1)

    def test_a_source_is_not_due_well_before_the_interval(self):
        self.make_source(last_attempt_at=NOW - timedelta(minutes=13))

        self.assertEqual(sync_all_ics_sources(now=NOW, fetch=self.fetch)["sources"], 0)

    def test_a_source_with_an_error_waits_longer(self):
        self.make_source(
            last_attempt_at=NOW - timedelta(minutes=30), last_sync_error="fetch_failed"
        )
        self.assertEqual(sync_all_ics_sources(now=NOW, fetch=self.fetch)["sources"], 0)

        IcsCalendarSource.objects.update(last_attempt_at=NOW - ERROR_INTERVAL)
        self.assertEqual(sync_all_ics_sources(now=NOW, fetch=self.fetch)["sources"], 1)

    def test_paused_sources_and_inactive_users_are_skipped(self):
        self.make_source(suffix="1", sync_enabled=False)
        gone = User.objects.create_user(username="gone", password="pass", is_active=False)
        self.make_source(user=gone, suffix="2")

        totals = sync_all_ics_sources(now=NOW, fetch=self.fetch)

        self.assertEqual(totals["sources"], 0)
        self.assertEqual(self.calls, [])

    def test_one_broken_source_does_not_stop_the_others(self):
        self.make_source(suffix="1")
        self.make_source(suffix="2")

        def fetch(url):
            if "0001" in url:
                raise RuntimeError(
                    f"boom {url}"
                )  # ein unerwarteter Fehler, der die Adresse enthält
            return self.fetch(url)

        with self.assertLogs("apps.calendar_sync.ics_sync", level="ERROR") as logs:
            totals = sync_all_ics_sources(now=NOW, fetch=fetch)

        self.assertEqual((totals["sources"], totals["created"], totals["errors"]), (2, 1, 1))
        self.assertTrue(BlockedTime.objects.filter(user=self.user).exists())
        # Weder die Adresse noch der Fehlertext dürfen im Protokoll stehen.
        self.assertNotIn("private-", "\n".join(logs.output))
        self.assertNotIn("boom", "\n".join(logs.output))

    def test_an_expected_error_counts_as_an_error_but_not_as_a_crash(self):
        self.make_source()

        def fetch(url):
            raise IcsError("fetch_failed")

        totals = sync_all_ics_sources(now=NOW, fetch=fetch)

        self.assertEqual((totals["sources"], totals["errors"]), (1, 1))


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SyncCalendarsCommandTest(TestCase):
    def test_the_command_still_prints_the_caldav_line_and_adds_one_for_addresses(self):
        out = StringIO()

        call_command("sync_calendars", stdout=out, no_color=True)

        text = out.getvalue()
        first, second = text.strip().splitlines()
        self.assertTrue(first.startswith("Calendar sync done: pushed="), first)
        self.assertTrue(second.startswith("Calendar address sync done: sources=0"), second)

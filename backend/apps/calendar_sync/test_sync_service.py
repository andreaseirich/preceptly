"""
Tests for the CalDAV sync engine, with CalDavClient mocked out entirely -
no real network/CalDAV server involved.

Sessions: pushed to the configured sessions_target calendar only, one-way.
BlockedTimes: imported from configured blocked_time_source calendar(s)
only, one-way. No conflicts are possible under this model since each type
only flows in one direction.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.caldav_client import ExternalEvent
from apps.calendar_sync.crypto import encrypt_password
from apps.calendar_sync.models import (
    CalendarConnection,
    ExternalCalendarEventMapping,
    SyncedCalendar,
)
from apps.calendar_sync.sync_service import sync_all_active_connections, sync_connection
from apps.contracts.models import Contract
from apps.lessons.models import Session

SESSIONS_CAL = "https://caldav.icloud.com/cal/nachhilfe/"
BLOCKED_CAL = "https://caldav.icloud.com/cal/privat/"
BLOCKED_CAL_2 = "https://caldav.icloud.com/cal/arbeit/"


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SyncConnectionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.connection = CalendarConnection.objects.create(
            user=self.user,
            provider="icloud",
            caldav_url="https://caldav.icloud.com/",
            caldav_username="tutor@example.com",
            encrypted_password=encrypt_password("app-specific-password"),
        )
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Muster",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )

    def _mock_client(self, **overrides):
        mock = MagicMock()
        mock.list_events.return_value = []
        mock.get_event.return_value = None
        mock.create_event.return_value = "etag-1"
        for key, value in overrides.items():
            setattr(mock, key, value)
        return mock

    def _add_sessions_target(self, url=SESSIONS_CAL, name="Nachhilfe"):
        return SyncedCalendar.objects.create(
            connection=self.connection,
            external_calendar_url=url,
            display_name=name,
            role=SyncedCalendar.ROLE_SESSIONS_TARGET,
        )

    def _add_blocked_source(self, url=BLOCKED_CAL, name="Privat"):
        return SyncedCalendar.objects.create(
            connection=self.connection,
            external_calendar_url=url,
            display_name=name,
            role=SyncedCalendar.ROLE_BLOCKED_TIME_SOURCE,
        )

    # --- no calendars configured at all -------------------------------

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_no_configured_calendars_does_nothing(self, mock_client_class):
        mock_client_class.return_value = self._mock_client()
        Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )
        BlockedTime.objects.create(
            user=self.user,
            title="Zahnarzt",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )

        result = sync_connection(self.connection)

        self.assertEqual(
            result,
            {"pushed": 0, "pulled": 0, "imported": 0, "conflicts": 0, "deleted": 0, "errors": 0},
        )

    # --- sessions: push-only --------------------------------------------

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_new_session_is_pushed_to_target_calendar(self, mock_client_class):
        self._add_sessions_target()
        mock = self._mock_client()
        mock_client_class.return_value = mock
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )

        result = sync_connection(self.connection)

        self.assertEqual(result["pushed"], 1)
        mock.create_event.assert_called_once()
        self.assertEqual(mock.create_event.call_args[0][0], SESSIONS_CAL)
        mapping = ExternalCalendarEventMapping.objects.get(
            content_type=ContentType.objects.get_for_model(Session), object_id=session.pk
        )
        self.assertEqual(mapping.connection, self.connection)

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_session_title_uses_calendar_title_template(self, mock_client_class):
        self._add_sessions_target()
        target = SyncedCalendar.objects.get(connection=self.connection)
        target.title_template = "Nachhilfe - {student}"
        target.save(update_fields=["title_template"])
        mock = self._mock_client()
        mock_client_class.return_value = mock
        Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )

        sync_connection(self.connection)

        mock.create_event.assert_called_once()
        # create_event(calendar_url, uid, title, start, end)
        self.assertEqual(mock.create_event.call_args[0][2], "Nachhilfe - Max Muster")

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_existing_event_at_same_time_is_adopted_not_duplicated(self, mock_client_class):
        """A tutor who already manually created a calendar entry at the
        exact time of a session must not get a second, duplicate event -
        the existing one is adopted into the mapping instead."""
        self._add_sessions_target()
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time().replace(microsecond=0),
            duration_minutes=60,
        )
        from apps.calendar_sync.sync_service import _session_bounds

        start, end = _session_bounds(session)
        manually_created = ExternalEvent(
            uid="tutors-own-uid-123",
            etag="etag-manual",
            summary="Nachhilfe Max",
            start=start,
            end=end,
        )
        mock = self._mock_client(list_events=MagicMock(return_value=[manually_created]))
        mock_client_class.return_value = mock

        result = sync_connection(self.connection)

        self.assertEqual(result["pushed"], 1)
        mock.create_event.assert_not_called()
        mapping = ExternalCalendarEventMapping.objects.get(
            content_type=ContentType.objects.get_for_model(Session), object_id=session.pk
        )
        self.assertEqual(mapping.external_uid, "tutors-own-uid-123")
        self.assertEqual(mapping.external_etag, "etag-manual")

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_event_at_different_time_is_not_adopted(self, mock_client_class):
        """An unrelated event that merely overlaps must never be claimed -
        only an exact start/end match counts as "the tutor's own entry"."""
        self._add_sessions_target()
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time().replace(microsecond=0),
            duration_minutes=60,
        )
        from apps.calendar_sync.sync_service import _session_bounds

        start, end = _session_bounds(session)
        unrelated = ExternalEvent(
            uid="unrelated-uid",
            etag="etag-x",
            summary="Anderer Termin",
            start=start + timedelta(minutes=15),
            end=end + timedelta(minutes=15),
        )
        mock = self._mock_client(list_events=MagicMock(return_value=[unrelated]))
        mock_client_class.return_value = mock

        sync_connection(self.connection)

        mock.create_event.assert_called_once()

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_update_after_adoption_targets_the_adopted_uid(self, mock_client_class):
        """Once an adopted (tutor-created) event's mapping exists, later
        pushes for that session must update *that* external_uid, not the
        Preceptly-generated one that was never actually created."""
        self._add_sessions_target()
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time().replace(microsecond=0),
            duration_minutes=60,
        )
        mapping = ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(Session),
            object_id=session.pk,
            external_uid="tutors-own-uid-123",
            external_etag="etag-manual",
            local_synced_at=session.updated_at - timedelta(minutes=5),
        )
        session.notes = "Thema geaendert"
        session.save(update_fields=["notes"])

        from apps.calendar_sync.sync_service import _session_bounds

        start, end = _session_bounds(session)
        current = ExternalEvent(
            uid="tutors-own-uid-123",
            etag="etag-manual",
            summary="Nachhilfe Max",
            start=start,
            end=end,
        )
        mock = self._mock_client(
            get_event=MagicMock(return_value=current),
            update_event=MagicMock(return_value="etag-updated"),
        )
        mock_client_class.return_value = mock

        sync_connection(self.connection)

        mock.get_event.assert_called_once_with(SESSIONS_CAL, "tutors-own-uid-123")
        mock.update_event.assert_called_once()
        self.assertEqual(mock.update_event.call_args[0][1], "tutors-own-uid-123")
        mapping.refresh_from_db()
        self.assertEqual(mapping.external_uid, "tutors-own-uid-123")

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_session_never_pulled_back_from_external_edit(self, mock_client_class):
        """The external copy of a pushed session can be edited freely -
        Preceptly must never overwrite the Session from it (it's a billed
        teaching record)."""
        self._add_sessions_target()
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )
        ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(Session),
            object_id=session.pk,
            external_uid=f"preceptly-session-{session.pk}@preceptly.de",
            external_etag="old-etag",
            local_synced_at=session.updated_at,
        )
        mock = self._mock_client(
            get_event=MagicMock(
                return_value=ExternalEvent(
                    uid=f"preceptly-session-{session.pk}@preceptly.de",
                    etag="changed-externally",
                    summary="Komplett anderer Titel",
                    start=timezone.now(),
                    end=timezone.now() + timedelta(hours=2),
                )
            )
        )
        mock_client_class.return_value = mock

        result = sync_connection(self.connection)

        # Nothing changed locally since the last sync, so nothing is
        # pushed either - the external-only change is simply ignored.
        self.assertEqual(result["pushed"], 0)
        self.assertEqual(result["conflicts"], 0)
        mock.update_event.assert_not_called()

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_externally_deleted_session_copy_is_not_recreated(self, mock_client_class):
        self._add_sessions_target()
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )
        mapping = ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(Session),
            object_id=session.pk,
            external_uid=f"preceptly-session-{session.pk}@preceptly.de",
            external_etag="old-etag",
            local_synced_at=session.updated_at - timedelta(minutes=5),
        )
        mock = self._mock_client(get_event=MagicMock(return_value=None))
        mock_client_class.return_value = mock

        sync_connection(self.connection)

        mock.create_event.assert_not_called()
        self.assertFalse(ExternalCalendarEventMapping.objects.filter(pk=mapping.pk).exists())
        self.assertTrue(Session.objects.filter(pk=session.pk).exists())

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_locally_deleted_session_deletes_pushed_copy(self, mock_client_class):
        self._add_sessions_target()
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )
        mapping = ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(Session),
            object_id=session.pk,
            external_uid=f"preceptly-session-{session.pk}@preceptly.de",
            external_etag="etag",
            local_synced_at=session.updated_at,
        )
        session.delete()
        mock = self._mock_client()
        mock_client_class.return_value = mock

        result = sync_connection(self.connection)

        self.assertEqual(result["deleted"], 1)
        mock.delete_event.assert_called_once_with(SESSIONS_CAL, mapping.external_uid)
        self.assertFalse(ExternalCalendarEventMapping.objects.filter(pk=mapping.pk).exists())

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_past_session_is_not_pushed(self, mock_client_class):
        """A lesson that already happened has nothing left to prepare for
        - it must never be pushed to the calendar in the first place."""
        self._add_sessions_target()
        mock = self._mock_client()
        mock_client_class.return_value = mock
        Session.objects.create(
            contract=self.contract,
            date=date.today() - timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )

        result = sync_connection(self.connection)

        self.assertEqual(result["pushed"], 0)
        mock.create_event.assert_not_called()

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_session_that_already_ended_today_is_not_pushed(self, mock_client_class):
        """Same as above but for a session dated today whose end time has
        already passed - the date alone isn't enough to tell. timezone.now()
        is pinned to a fixed point on the session's day (only around the
        sync_connection() call itself, so setup's own auto_now_add fields
        are unaffected) so this can't flake depending on what wall-clock
        time the test happens to run at."""
        self._add_sessions_target()
        mock = self._mock_client()
        mock_client_class.return_value = mock
        Session.objects.create(
            contract=self.contract,
            date=date.today(),
            start_time=time(9, 0),
            duration_minutes=60,
        )
        fixed_now = timezone.make_aware(datetime.combine(date.today(), time(12, 0)))

        with patch("apps.calendar_sync.sync_service.timezone.now", return_value=fixed_now):
            result = sync_connection(self.connection)

        self.assertEqual(result["pushed"], 0)
        mock.create_event.assert_not_called()

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_session_that_became_past_has_its_pushed_copy_deleted(self, mock_client_class):
        """A session that was pushed while still upcoming, and has since
        happened, must have its calendar copy removed on the next sync -
        not just be skipped from then on."""
        self._add_sessions_target()
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() - timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )
        mapping = ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(Session),
            object_id=session.pk,
            external_uid=f"preceptly-session-{session.pk}@preceptly.de",
            external_etag="etag",
            local_synced_at=session.updated_at,
        )
        mock = self._mock_client()
        mock_client_class.return_value = mock

        result = sync_connection(self.connection)

        self.assertEqual(result["deleted"], 1)
        mock.delete_event.assert_called_once_with(SESSIONS_CAL, mapping.external_uid)
        self.assertFalse(ExternalCalendarEventMapping.objects.filter(pk=mapping.pk).exists())
        self.assertTrue(Session.objects.filter(pk=session.pk).exists())

    # --- blocked times: pull-only ---------------------------------------

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_new_external_event_is_imported_as_blocked_time(self, mock_client_class):
        self._add_blocked_source()
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        mock = self._mock_client(
            list_events=MagicMock(
                return_value=[
                    ExternalEvent(
                        uid="external-uid-1",
                        etag="etag-x",
                        summary="Uni-Vorlesung",
                        start=start,
                        end=end,
                    )
                ]
            )
        )
        mock_client_class.return_value = mock

        result = sync_connection(self.connection)

        self.assertEqual(result["imported"], 1)
        mock.list_events.assert_called_once()
        self.assertEqual(mock.list_events.call_args[0][0], BLOCKED_CAL)
        bt = BlockedTime.objects.get(user=self.user, title="Uni-Vorlesung")
        mapping = ExternalCalendarEventMapping.objects.get(external_uid="external-uid-1")
        self.assertEqual(mapping.object_id, bt.pk)

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_blocked_time_created_locally_is_never_pushed(self, mock_client_class):
        self._add_blocked_source()
        BlockedTime.objects.create(
            user=self.user,
            title="Privater Termin",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )
        mock = self._mock_client()
        mock_client_class.return_value = mock

        result = sync_connection(self.connection)

        mock.create_event.assert_not_called()
        mock.update_event.assert_not_called()
        self.assertEqual(result["pushed"], 0)

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_externally_updated_event_updates_the_blocked_time(self, mock_client_class):
        source = self._add_blocked_source()
        bt = BlockedTime.objects.create(
            user=self.user,
            title="Alter Titel",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )
        ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(BlockedTime),
            object_id=bt.pk,
            external_uid="ext-uid-2",
            external_etag="old-etag",
            local_synced_at=bt.updated_at,
        )
        new_start = timezone.now() + timedelta(days=3)
        new_end = new_start + timedelta(hours=1)
        mock = self._mock_client(
            list_events=MagicMock(
                return_value=[
                    ExternalEvent(
                        uid="ext-uid-2",
                        etag="new-etag",
                        summary="Neuer Titel",
                        start=new_start,
                        end=new_end,
                    )
                ]
            )
        )
        mock_client_class.return_value = mock
        del source  # only needed to create the SyncedCalendar row

        result = sync_connection(self.connection)

        self.assertEqual(result["pulled"], 1)
        bt.refresh_from_db()
        self.assertEqual(bt.title, "Neuer Titel")

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_externally_deleted_event_deletes_the_blocked_time(self, mock_client_class):
        self._add_blocked_source()
        bt = BlockedTime.objects.create(
            user=self.user,
            title="Wird geloescht",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )
        ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(BlockedTime),
            object_id=bt.pk,
            external_uid="ext-uid-3",
            external_etag="etag",
            local_synced_at=bt.updated_at,
        )
        mock = self._mock_client(list_events=MagicMock(return_value=[]))
        mock_client_class.return_value = mock

        result = sync_connection(self.connection)

        self.assertEqual(result["deleted"], 1)
        self.assertFalse(BlockedTime.objects.filter(pk=bt.pk).exists())

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_mapping_from_one_source_not_deleted_when_missing_from_another_sources_listing(
        self, mock_client_class
    ):
        """Regression: a tutor with two blocked_time_source calendars must
        not have a mapping deleted just because it wasn't in the *other*
        source's listing - only when it's absent from all of them."""
        self._add_blocked_source(url=BLOCKED_CAL, name="Privat")
        self._add_blocked_source(url=BLOCKED_CAL_2, name="Arbeit")
        bt = BlockedTime.objects.create(
            user=self.user,
            title="Aus Privat importiert",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )
        ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(BlockedTime),
            object_id=bt.pk,
            external_uid="privat-uid-1",
            external_etag="etag",
            local_synced_at=bt.updated_at,
        )

        def list_events_side_effect(calendar_url, start, end):
            if calendar_url == BLOCKED_CAL:
                return [
                    ExternalEvent(
                        uid="privat-uid-1",
                        etag="etag",
                        summary="Aus Privat importiert",
                        start=bt.start_datetime,
                        end=bt.end_datetime,
                    )
                ]
            return []  # BLOCKED_CAL_2 doesn't have this UID - and never did

        mock = self._mock_client(list_events=MagicMock(side_effect=list_events_side_effect))
        mock_client_class.return_value = mock

        result = sync_connection(self.connection)

        self.assertEqual(result["deleted"], 0)
        self.assertTrue(BlockedTime.objects.filter(pk=bt.pk).exists())

    # --- connection-level ------------------------------------------------

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_connect_failure_records_error_without_raising(self, mock_client_class):
        mock_client_class.side_effect = Exception("connection refused")

        result = sync_connection(self.connection)

        self.assertEqual(result["errors"], 1)
        self.connection.refresh_from_db()
        self.assertIn("connection refused", self.connection.last_sync_error)

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_disabled_connection_is_skipped(self, mock_client_class):
        self.connection.sync_enabled = False
        self.connection.save(update_fields=["sync_enabled"])

        result = sync_connection(self.connection)

        mock_client_class.assert_not_called()
        self.assertEqual(result["pushed"], 0)

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_summary_is_persisted_on_connection(self, mock_client_class):
        self._add_sessions_target()
        mock_client_class.return_value = self._mock_client()
        Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )

        result = sync_connection(self.connection)

        self.connection.refresh_from_db()
        self.assertEqual(self.connection.last_sync_summary, result)


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class SyncAllActiveConnectionsTest(TestCase):
    """Regression: apps/calendar_sync/management/commands/sync_calendars.py
    (the periodic cron job) imports this function by name - it silently
    disappeared during the two-way -> one-way rewrite, so the cron job
    failed on every single run (ImportError) until this was restored."""

    def setUp(self):
        self.user1 = User.objects.create_user(username="tutor_a", password="pass")
        self.user2 = User.objects.create_user(username="tutor_b", password="pass")
        self.connection1 = CalendarConnection.objects.create(
            user=self.user1,
            provider="icloud",
            caldav_url="https://caldav.icloud.com/",
            caldav_username="a@example.com",
            encrypted_password=encrypt_password("pw-a"),
        )
        self.connection2 = CalendarConnection.objects.create(
            user=self.user2,
            provider="icloud",
            caldav_url="https://caldav.icloud.com/",
            caldav_username="b@example.com",
            encrypted_password=encrypt_password("pw-b"),
            sync_enabled=False,
        )

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_only_syncs_enabled_connections(self, mock_client_class):
        mock = MagicMock()
        mock.list_events.return_value = []
        mock.get_event.return_value = None
        mock.create_event.return_value = "etag-1"
        mock_client_class.return_value = mock

        totals = sync_all_active_connections()

        mock_client_class.assert_called_once_with(
            self.connection1.caldav_url, self.connection1.caldav_username, "pw-a"
        )
        self.assertEqual(
            totals,
            {"pushed": 0, "pulled": 0, "imported": 0, "conflicts": 0, "deleted": 0, "errors": 0},
        )

    @patch("apps.calendar_sync.sync_service.sync_connection")
    def test_one_connections_exception_does_not_abort_the_rest(self, mock_sync_connection):
        self.connection2.sync_enabled = True
        self.connection2.save(update_fields=["sync_enabled"])

        def side_effect(connection):
            if connection.pk == self.connection1.pk:
                raise RuntimeError("boom")
            return {
                "pushed": 1,
                "pulled": 0,
                "imported": 0,
                "conflicts": 0,
                "deleted": 0,
                "errors": 0,
            }

        mock_sync_connection.side_effect = side_effect

        totals = sync_all_active_connections()

        self.assertEqual(mock_sync_connection.call_count, 2)
        self.assertEqual(totals["errors"], 1)
        self.assertEqual(totals["pushed"], 1)

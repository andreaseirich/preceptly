"""
Tests for the CalDAV sync engine, with CalDavClient mocked out entirely -
no real network/CalDAV server involved.
"""

from datetime import date, timedelta
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
from apps.calendar_sync.models import CalendarConnection, ExternalCalendarEventMapping, SyncConflict
from apps.calendar_sync.sync_service import sync_connection
from apps.contracts.models import Contract
from apps.lessons.models import Session


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

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_new_blocked_time_is_pushed_and_mapped(self, mock_client_class):
        mock_client_class.return_value = self._mock_client()
        bt = BlockedTime.objects.create(
            user=self.user,
            title="Zahnarzt",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )

        result = sync_connection(self.connection)

        self.assertEqual(result["pushed"], 1)
        self.assertEqual(
            ExternalCalendarEventMapping.objects.filter(
                content_type=ContentType.objects.get_for_model(BlockedTime), object_id=bt.pk
            ).count(),
            1,
        )

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_new_session_is_pushed_and_mapped(self, mock_client_class):
        mock_client_class.return_value = self._mock_client()
        session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=timezone.now().time(),
            duration_minutes=60,
        )

        result = sync_connection(self.connection)

        self.assertEqual(result["pushed"], 1)
        self.assertEqual(
            ExternalCalendarEventMapping.objects.filter(
                content_type=ContentType.objects.get_for_model(Session), object_id=session.pk
            ).count(),
            1,
        )

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_new_external_event_is_imported_as_blocked_time(self, mock_client_class):
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        mock_client_class.return_value = self._mock_client(
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

        result = sync_connection(self.connection)

        self.assertEqual(result["imported"], 1)
        bt = BlockedTime.objects.get(user=self.user, title="Uni-Vorlesung")
        mapping = ExternalCalendarEventMapping.objects.get(external_uid="external-uid-1")
        self.assertEqual(mapping.object_id, bt.pk)

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_both_sides_changed_creates_conflict_not_overwrite(self, mock_client_class):
        bt = BlockedTime.objects.create(
            user=self.user,
            title="Zahnarzt",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )
        mapping = ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(BlockedTime),
            object_id=bt.pk,
            external_uid=f"preceptly-blockedtime-{bt.pk}@preceptly.de",
            external_etag="old-etag",
            # Explicitly before bt.updated_at rather than bt.updated_at
            # itself - two saves in the same test can land in the same
            # microsecond tick, which would make a plain ">" comparison
            # flaky depending on timer resolution.
            local_synced_at=bt.updated_at - timedelta(minutes=5),
            external_synced_at=timezone.now(),
        )
        # Local side changes after the last sync snapshot.
        bt.title = "Zahnarzt (verschoben)"
        bt.save(update_fields=["title"])

        mock_client_class.return_value = self._mock_client(
            get_event=MagicMock(
                return_value=ExternalEvent(
                    uid=mapping.external_uid,
                    etag="new-etag-from-server",
                    summary="Zahnarzt (extern geaendert)",
                    start=bt.start_datetime,
                    end=bt.end_datetime,
                )
            )
        )

        result = sync_connection(self.connection)

        self.assertEqual(result["conflicts"], 1)
        self.assertEqual(SyncConflict.objects.filter(mapping=mapping).count(), 1)
        bt.refresh_from_db()
        self.assertEqual(bt.title, "Zahnarzt (verschoben)")  # not silently overwritten

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
    def test_externally_deleted_blocked_time_is_removed_locally(self, mock_client_class):
        bt = BlockedTime.objects.create(
            user=self.user,
            title="Zahnarzt",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )
        ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(BlockedTime),
            object_id=bt.pk,
            external_uid=f"preceptly-blockedtime-{bt.pk}@preceptly.de",
            external_etag="old-etag",
            local_synced_at=bt.updated_at,
            external_synced_at=timezone.now(),
        )
        mock_client_class.return_value = self._mock_client(get_event=MagicMock(return_value=None))

        result = sync_connection(self.connection)

        self.assertEqual(result["deleted"], 1)
        self.assertFalse(BlockedTime.objects.filter(pk=bt.pk).exists())
        self.assertFalse(ExternalCalendarEventMapping.objects.filter(object_id=bt.pk).exists())

    @patch("apps.calendar_sync.sync_service.CalDavClient")
    def test_externally_deleted_session_keeps_the_session(self, mock_client_class):
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
            local_synced_at=session.updated_at,
            external_synced_at=timezone.now(),
        )
        mock_client_class.return_value = self._mock_client(get_event=MagicMock(return_value=None))

        result = sync_connection(self.connection)

        self.assertEqual(result["deleted"], 1)
        self.assertTrue(Session.objects.filter(pk=session.pk).exists())
        self.assertFalse(ExternalCalendarEventMapping.objects.filter(pk=mapping.pk).exists())

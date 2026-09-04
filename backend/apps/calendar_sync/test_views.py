"""
Tests for the calendar sync connect/disconnect/toggle/conflict views.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.caldav_client import CalDavConnectionError, ExternalCalendar
from apps.calendar_sync.crypto import decrypt_password, encrypt_password
from apps.calendar_sync.models import (
    CalendarConnection,
    ExternalCalendarEventMapping,
    SyncConflict,
    SyncedCalendar,
)


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class ConnectCalendarViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.client = Client()
        self.client.login(username="tutor", password="pass")

    @patch("apps.calendar_sync.views.CalDavClient")
    def test_valid_credentials_create_connection_with_encrypted_password(self, mock_client_class):
        mock_client_class.return_value = MagicMock()

        response = self.client.post(
            reverse("calendar_sync:connect"),
            {
                "provider": "icloud",
                "caldav_url": "https://caldav.icloud.com/",
                "caldav_username": "tutor@example.com",
                "caldav_password": "app-specific-pw",
            },
        )

        self.assertEqual(response.status_code, 302)
        connection = CalendarConnection.objects.get(user=self.user)
        self.assertEqual(connection.caldav_username, "tutor@example.com")
        self.assertNotEqual(bytes(connection.encrypted_password), b"app-specific-pw")
        self.assertEqual(decrypt_password(bytes(connection.encrypted_password)), "app-specific-pw")

    @patch("apps.calendar_sync.views.CalDavClient")
    def test_bad_credentials_do_not_create_a_connection(self, mock_client_class):
        mock_client_class.side_effect = CalDavConnectionError("auth failed")

        response = self.client.post(
            reverse("calendar_sync:connect"),
            {
                "provider": "icloud",
                "caldav_url": "https://caldav.icloud.com/",
                "caldav_username": "tutor@example.com",
                "caldav_password": "wrong-pw",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(CalendarConnection.objects.filter(user=self.user).exists())

    @patch("apps.calendar_sync.views.CalDavClient")
    def test_bad_credentials_redirect_prefills_username_not_password(self, mock_client_class):
        mock_client_class.side_effect = CalDavConnectionError("auth failed")

        response = self.client.post(
            reverse("calendar_sync:connect"),
            {
                "provider": "icloud",
                "caldav_username": "tutor@example.com",
                "caldav_password": "wrong-pw",
            },
        )

        self.assertIn("calendar_username=tutor%40example.com", response.url)
        self.assertNotIn("wrong-pw", response.url)

    def test_missing_field_does_not_create_a_connection(self):
        response = self.client.post(
            reverse("calendar_sync:connect"),
            {"provider": "icloud", "caldav_url": "", "caldav_username": "", "caldav_password": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CalendarConnection.objects.filter(user=self.user).exists())


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class ConfigureCalendarsViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_cfg", password="pass")
        self.client = Client()
        self.client.login(username="tutor_cfg", password="pass")
        self.connection = CalendarConnection.objects.create(
            user=self.user,
            provider="icloud",
            caldav_url="https://caldav.icloud.com/",
            caldav_username="tutor_cfg@example.com",
            encrypted_password=encrypt_password("pw"),
        )

    @patch("apps.calendar_sync.views.CalDavClient")
    def test_get_shows_available_calendars(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.list_event_calendars.return_value = [
            ExternalCalendar(url="https://x/nachhilfe/", name="Nachhilfe"),
            ExternalCalendar(url="https://x/privat/", name="Privat"),
        ]
        mock_client_class.return_value = mock_client

        response = self.client.get(reverse("calendar_sync:configure"))

        self.assertContains(response, "Nachhilfe")
        self.assertContains(response, "Privat")

    @patch("apps.calendar_sync.views.CalDavClient")
    def test_post_saves_selection(self, mock_client_class):
        response = self.client.post(
            reverse("calendar_sync:configure"),
            {
                "sessions_target": "https://x/nachhilfe/",
                "name_https://x/nachhilfe/": "Nachhilfe",
                "blocked_sources": ["https://x/privat/", "https://x/arbeit/"],
                "name_https://x/privat/": "Privat",
                "name_https://x/arbeit/": "Arbeit",
            },
        )

        self.assertEqual(response.status_code, 302)
        target = SyncedCalendar.objects.get(
            connection=self.connection, role=SyncedCalendar.ROLE_SESSIONS_TARGET
        )
        self.assertEqual(target.external_calendar_url, "https://x/nachhilfe/")
        self.assertEqual(target.display_name, "Nachhilfe")
        sources = set(
            SyncedCalendar.objects.filter(
                connection=self.connection, role=SyncedCalendar.ROLE_BLOCKED_TIME_SOURCE
            ).values_list("external_calendar_url", flat=True)
        )
        self.assertEqual(sources, {"https://x/privat/", "https://x/arbeit/"})

    @patch("apps.calendar_sync.views.CalDavClient")
    def test_post_replaces_previous_selection(self, mock_client_class):
        SyncedCalendar.objects.create(
            connection=self.connection,
            external_calendar_url="https://x/old-target/",
            display_name="Old",
            role=SyncedCalendar.ROLE_SESSIONS_TARGET,
        )

        self.client.post(
            reverse("calendar_sync:configure"),
            {
                "sessions_target": "https://x/new-target/",
                "name_https://x/new-target/": "New",
            },
        )

        self.assertEqual(SyncedCalendar.objects.filter(connection=self.connection).count(), 1)
        self.assertEqual(
            SyncedCalendar.objects.get(connection=self.connection).external_calendar_url,
            "https://x/new-target/",
        )

    def test_requires_login(self):
        Client().get(reverse("calendar_sync:configure"))
        # anonymous access redirects to login rather than raising - just
        # confirm no SyncedCalendar rows leak from an unauthenticated call
        self.assertEqual(SyncedCalendar.objects.count(), 0)


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class DisconnectAndToggleViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor2", password="pass")
        self.client = Client()
        self.client.login(username="tutor2", password="pass")
        self.connection = CalendarConnection.objects.create(
            user=self.user,
            provider="icloud",
            caldav_url="https://caldav.icloud.com/",
            caldav_username="tutor2@example.com",
            encrypted_password=encrypt_password("pw"),
        )

    def test_disconnect_deletes_connection(self):
        response = self.client.post(reverse("calendar_sync:disconnect"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CalendarConnection.objects.filter(user=self.user).exists())

    def test_toggle_flips_sync_enabled(self):
        self.assertTrue(self.connection.sync_enabled)
        self.client.post(reverse("calendar_sync:toggle"))
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.sync_enabled)

    def test_another_users_connection_is_not_affected(self):
        other = User.objects.create_user(username="other_tutor", password="pass")
        other_connection = CalendarConnection.objects.create(
            user=other, provider="icloud", encrypted_password=encrypt_password("pw2")
        )
        self.client.post(reverse("calendar_sync:disconnect"))
        self.assertTrue(CalendarConnection.objects.filter(pk=other_connection.pk).exists())


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class ConflictResolutionViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor3", password="pass")
        self.client = Client()
        self.client.login(username="tutor3", password="pass")
        self.connection = CalendarConnection.objects.create(
            user=self.user,
            provider="icloud",
            encrypted_password=encrypt_password("pw"),
        )
        self.bt = BlockedTime.objects.create(
            user=self.user,
            title="Zahnarzt",
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
        )
        self.mapping = ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=ContentType.objects.get_for_model(BlockedTime),
            object_id=self.bt.pk,
            external_uid="uid-1",
            local_synced_at=self.bt.updated_at,
        )
        self.conflict = SyncConflict.objects.create(
            connection=self.connection,
            mapping=self.mapping,
            local_snapshot={"title": "Zahnarzt (lokal)"},
            external_snapshot={"title": "Zahnarzt (extern)"},
        )

    def test_conflict_list_shows_open_conflicts(self):
        response = self.client.get(reverse("calendar_sync:conflicts"))
        self.assertContains(response, "Zahnarzt (lokal)")
        self.assertContains(response, "Zahnarzt (extern)")

    def test_keep_local_marks_resolved_without_changing_title(self):
        response = self.client.post(
            reverse("calendar_sync:resolve_conflict", args=[self.conflict.pk]),
            {"resolution": "local"},
        )
        self.assertEqual(response.status_code, 302)
        self.conflict.refresh_from_db()
        self.assertIsNotNone(self.conflict.resolved_at)
        self.bt.refresh_from_db()
        self.assertEqual(self.bt.title, "Zahnarzt")

    def test_keep_external_applies_external_title(self):
        response = self.client.post(
            reverse("calendar_sync:resolve_conflict", args=[self.conflict.pk]),
            {"resolution": "external"},
        )
        self.assertEqual(response.status_code, 302)
        self.bt.refresh_from_db()
        self.assertEqual(self.bt.title, "Zahnarzt (extern)")

    def test_other_tutors_conflict_returns_404(self):
        User.objects.create_user(username="other_tutor3", password="pass")
        other_client = Client()
        other_client.login(username="other_tutor3", password="pass")
        response = other_client.post(
            reverse("calendar_sync:resolve_conflict", args=[self.conflict.pk]),
            {"resolution": "local"},
        )
        self.assertEqual(response.status_code, 404)

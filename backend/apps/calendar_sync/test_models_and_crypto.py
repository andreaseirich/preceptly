"""
Tests for the CalDAV password encryption helper and the calendar sync
models' basic constraints.
"""

from datetime import date, time
from decimal import Decimal

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.test import TestCase, override_settings

from apps.calendar_sync.crypto import (
    CalendarCredentialError,
    decrypt_password,
    encrypt_password,
)
from apps.calendar_sync.models import CalendarConnection, ExternalCalendarEventMapping
from apps.contracts.models import Contract
from apps.lessons.models import Lesson


class CalendarCredentialCryptoTest(TestCase):
    @override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_encrypt_then_decrypt_roundtrips(self):
        encrypted = encrypt_password("super-secret-app-password")
        self.assertEqual(decrypt_password(encrypted), "super-secret-app-password")

    @override_settings(CALDAV_ENCRYPTION_KEY="")
    def test_missing_key_raises(self):
        with self.assertRaises(CalendarCredentialError):
            encrypt_password("whatever")

    @override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_decrypt_with_wrong_key_raises(self):
        encrypted = encrypt_password("super-secret-app-password")
        with override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            with self.assertRaises(CalendarCredentialError):
                decrypt_password(encrypted)


class CalendarConnectionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")

    def test_one_connection_per_user(self):
        CalendarConnection.objects.create(user=self.user, provider="icloud")
        with self.assertRaises(IntegrityError):
            CalendarConnection.objects.create(user=self.user, provider="icloud")


class ExternalCalendarEventMappingModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor2", password="pass")
        self.connection = CalendarConnection.objects.create(user=self.user, provider="icloud")
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Muster",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract, date=date.today(), start_time=time(14, 0), duration_minutes=60
        )
        self.content_type = ContentType.objects.get_for_model(Lesson)

    def test_mapping_unique_per_local_object(self):
        from django.utils import timezone

        ExternalCalendarEventMapping.objects.create(
            connection=self.connection,
            content_type=self.content_type,
            object_id=self.lesson.pk,
            external_uid="uid-1",
            local_synced_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError):
            ExternalCalendarEventMapping.objects.create(
                connection=self.connection,
                content_type=self.content_type,
                object_id=self.lesson.pk,
                external_uid="uid-2",
                local_synced_at=timezone.now(),
            )

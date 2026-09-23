"""Zugriffsprotokollierung: was gespeichert wird, was nicht, und wie lange."""

import hashlib
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.middleware import purge_old_request_logs
from apps.core.models import RequestLog


class RequestLogMiddlewareTest(TestCase):
    def setUp(self):
        cache.clear()
        RequestLog.objects.all().delete()

    def test_page_view_is_logged(self):
        self.client.get(reverse("core:login"), HTTP_USER_AGENT="Testbrowser/1.0")

        entry = RequestLog.objects.get()
        self.assertEqual(entry.path, reverse("core:login"))
        self.assertEqual(entry.method, "GET")
        self.assertEqual(entry.status_code, 200)
        self.assertEqual(entry.user_agent, "Testbrowser/1.0")
        self.assertIsNotNone(entry.response_ms)

    def test_health_check_and_static_are_not_logged(self):
        self.client.get("/health/")
        self.client.get("/static/css/does-not-exist.css")

        self.assertEqual(RequestLog.objects.count(), 0)

    def test_session_key_is_stored_pseudonymously(self):
        user = User.objects.create_user(username="tutor", password="pass-für-den-test")
        self.client.force_login(user)
        RequestLog.objects.all().delete()

        self.client.get(reverse("core:login"))

        entry = RequestLog.objects.latest("timestamp")
        session_key = self.client.session.session_key
        self.assertTrue(session_key)
        self.assertNotEqual(entry.session_key, session_key)
        self.assertNotIn(session_key, entry.session_key)
        self.assertEqual(
            entry.session_key,
            hashlib.sha256(session_key.encode()).hexdigest()[:40],
        )

    def test_client_ip_is_taken_from_the_trusted_proxy_header(self):
        self.client.get(
            reverse("core:login"),
            HTTP_X_FORWARDED_FOR="203.0.113.7, 100.64.0.1",
            REMOTE_ADDR="100.64.0.1",
        )

        self.assertEqual(RequestLog.objects.latest("timestamp").ip, "203.0.113.7")


class RequestLogRetentionTest(TestCase):
    def setUp(self):
        cache.clear()
        RequestLog.objects.all().delete()

    def _make_entry(self, age_days):
        entry = RequestLog.objects.create(path="/alt/", method="GET", status_code=200)
        RequestLog.objects.filter(pk=entry.pk).update(
            timestamp=timezone.now() - timedelta(days=age_days)
        )
        return entry

    @override_settings(REQUEST_LOG_RETENTION_DAYS=30)
    def test_entries_older_than_the_retention_are_deleted(self):
        old = self._make_entry(31)
        recent = self._make_entry(29)

        deleted = purge_old_request_logs()

        self.assertEqual(deleted, 1)
        self.assertFalse(RequestLog.objects.filter(pk=old.pk).exists())
        self.assertTrue(RequestLog.objects.filter(pk=recent.pk).exists())

    def test_management_command_accepts_a_custom_retention(self):
        old = self._make_entry(10)
        recent = self._make_entry(2)

        call_command("purge_request_logs", "--days", "5")

        self.assertFalse(RequestLog.objects.filter(pk=old.pk).exists())
        self.assertTrue(RequestLog.objects.filter(pk=recent.pk).exists())

    @override_settings(REQUEST_LOG_RETENTION_DAYS=30)
    def test_purge_runs_at_most_once_a_day(self):
        self._make_entry(31)
        self.client.get(reverse("core:login"))
        self.assertFalse(RequestLog.objects.filter(path="/alt/").exists())

        # Zweiter Aufruf: Sperre steht, ein neuer alter Eintrag bleibt liegen.
        self._make_entry(31)
        self.client.get(reverse("core:login"))
        self.assertTrue(RequestLog.objects.filter(path="/alt/").exists())

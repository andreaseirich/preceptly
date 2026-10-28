"""Tageszähler und die Zählung der Honeypot-Abweisungen.

Auftrag von Andreas, 28.10.2026 ("Ja, mach die Abweisungen zählbar"). Eine Abweisung hinterlässt kein Konto; der Zähler
(ohne personenbezogene Daten) macht sie auf /dev/stats/ sichtbar.
"""

import datetime as dt
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.counters import REGISTRATION_HONEYPOT, count_event, counts_by_day, total_count
from apps.core.models import DailyCounter
from apps.core.views_stats import SESSION_KEY


class CounterTest(TestCase):
    def test_the_first_event_creates_the_row(self):
        count_event("demo")

        row = DailyCounter.objects.get(name="demo")
        self.assertEqual((row.day, row.count), (timezone.localdate(), 1))

    def test_further_events_of_the_same_day_raise_the_same_row(self):
        for _ in range(3):
            count_event("demo")

        self.assertEqual(DailyCounter.objects.filter(name="demo").count(), 1)
        self.assertEqual(DailyCounter.objects.get(name="demo").count, 3)

    def test_other_names_and_other_days_count_separately(self):
        today = timezone.localdate()
        count_event("a")
        count_event("b")
        count_event("a", day=today - dt.timedelta(days=1))

        self.assertEqual(DailyCounter.objects.count(), 3)
        self.assertEqual(total_count("a"), 2)
        self.assertEqual(total_count("b"), 1)

    def test_a_row_exists_only_once_per_name_and_day(self):
        count_event("demo")

        with self.assertRaises(IntegrityError), transaction.atomic():
            DailyCounter.objects.create(name="demo", day=timezone.localdate(), count=1)

    def test_counts_by_day_lists_every_day_oldest_first_with_zeros(self):
        today = timezone.localdate()
        count_event("demo", day=today)
        count_event("demo", day=today)
        count_event("demo", day=today - dt.timedelta(days=2))
        count_event("demo", day=today - dt.timedelta(days=30))  # außerhalb des Fensters

        days = counts_by_day("demo", 4)

        self.assertEqual([d["count"] for d in days], [0, 1, 0, 2])
        self.assertEqual(days[-1]["day"], today)
        self.assertEqual(days[0]["day"], today - dt.timedelta(days=3))

    def test_total_is_zero_without_rows(self):
        self.assertEqual(total_count("nichts"), 0)

    def test_it_stores_no_personal_data(self):
        fields = {field.name for field in DailyCounter._meta.get_fields()}

        self.assertEqual(fields, {"id", "name", "day", "count"})


class RegistrationCountingTest(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("core:register")

    def post(self, **extra):
        data = {
            "username": "botuser",
            "email": "bot@example.com",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
            "avv_consent": "on",
        }
        data.update(extra)
        return self.client.post(self.url, data)

    def today(self):
        return total_count(REGISTRATION_HONEYPOT)

    def test_a_rejection_is_counted(self):
        self.post(homepage="http://spam.example")

        self.assertEqual(self.today(), 1)
        self.assertEqual(counts_by_day(REGISTRATION_HONEYPOT, 1)[0]["count"], 1)

    def test_every_rejection_counts(self):
        for _ in range(3):
            self.post(homepage="x")

        self.assertEqual(self.today(), 3)

    def test_a_normal_registration_is_not_counted(self):
        self.post()

        self.assertEqual(self.today(), 0)
        self.assertTrue(User.objects.filter(username="botuser").exists())

    def test_other_form_errors_are_not_counted(self):
        self.post(password2="anders")  # Passwörter stimmen nicht überein
        self.post(email="")  # Pflichtfeld fehlt

        self.assertEqual(self.today(), 0)

    def test_throttled_attempts_are_not_counted_as_rejections(self):
        for _ in range(7):
            self.post(homepage="x")

        # nur die Versuche, die das Formular überhaupt erreicht haben (die Drosselung greift vorher)
        self.assertEqual(self.today(), 5)

    def test_a_broken_counter_does_not_break_the_response(self):
        with (
            mock.patch("apps.core.views_auth.count_event", side_effect=RuntimeError("kaputt")),
            self.assertLogs("apps.core.views_auth", level="WARNING") as logs,
        ):
            response = self.post(homepage="x")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrierung fehlgeschlagen. Bitte versuche es erneut.")
        self.assertFalse(User.objects.filter(username="botuser").exists())
        self.assertIn("Honeypot counter", "\n".join(logs.output))


class StatsPageTest(TestCase):
    def setUp(self):
        session = self.client.session
        session[SESSION_KEY] = True
        session.save()
        today = timezone.localdate()
        DailyCounter.objects.create(name=REGISTRATION_HONEYPOT, day=today, count=3)
        DailyCounter.objects.create(
            name=REGISTRATION_HONEYPOT, day=today - dt.timedelta(days=1), count=2
        )
        DailyCounter.objects.create(
            name=REGISTRATION_HONEYPOT, day=today - dt.timedelta(days=10), count=4
        )
        DailyCounter.objects.create(name="anderer", day=today, count=99)

    def value(self, html, label):
        match = re.search(
            rf"<tr><td>{re.escape(label)}</td><td><strong>(\d+)</strong></td></tr>", html
        )
        self.assertIsNotNone(match, label)
        return int(match.group(1))

    def test_the_page_shows_today_the_week_and_the_total(self):
        html = self.client.get(reverse("core:dev_stats")).content.decode()

        self.assertEqual(self.value(html, "Vom Honeypot abgewiesen, heute"), 3)
        self.assertEqual(self.value(html, "Vom Honeypot abgewiesen, letzte 7 Tage"), 5)
        self.assertEqual(self.value(html, "Vom Honeypot abgewiesen, gesamt (seit Zählbeginn)"), 9)

    def test_without_any_rejections_the_page_shows_zeros(self):
        DailyCounter.objects.all().delete()

        html = self.client.get(reverse("core:dev_stats")).content.decode()

        self.assertEqual(self.value(html, "Vom Honeypot abgewiesen, heute"), 0)
        self.assertEqual(self.value(html, "Vom Honeypot abgewiesen, gesamt (seit Zählbeginn)"), 0)

    def test_the_page_stays_locked_without_the_password_session(self):
        response = self.client_class().get(reverse("core:dev_stats"))  # neue Sitzung ohne Anmeldung

        self.assertNotContains(response, "Vom Honeypot abgewiesen")

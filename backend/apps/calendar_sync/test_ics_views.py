"""Kalender per Adresse: hinzufügen, abgleichen, pausieren, entfernen (Ansichten und Einstellungsseite)."""

from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.crypto import decrypt_password, encrypt_password
from apps.calendar_sync.ics_import import IcsError
from apps.calendar_sync.models import IcsCalendarSource
from apps.calendar_sync.test_ics_import import event, ics

URL = "https://calendar.google.com/calendar/ical/anna%40gmail.com/private-0123456789abcdef0123/basic.ics"
FETCH = "apps.calendar_sync.views_ics.fetch_ics"


def future_feed(uid="m1@google.com", summary="Vorlesung"):
    day = (timezone.now() + timedelta(days=10)).strftime("%Y%m%d")
    return ics(
        event(f"UID:{uid}", f"DTSTART:{day}T100000Z", f"DTEND:{day}T113000Z", f"SUMMARY:{summary}"),
        header="X-WR-TIMEZONE:Europe/Berlin",
    )


def texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class IcsViewsTestCase(TestCase):
    def setUp(self):
        cache.clear()  # die Rate-Limits zählen im Cache und sollen nicht von Test zu Test wandern
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.client.defaults["HTTP_ACCEPT_LANGUAGE"] = (
            "en"  # die Prüfungen unten lesen die englischen Texte
        )
        self.client.login(username="tutor", password="pass")

    def make_source(self, user=None, url=URL, name="Privat", **fields):
        return IcsCalendarSource.objects.create(
            user=user or self.user,
            name=name,
            encrypted_url=encrypt_password(url),
            url_hash=IcsCalendarSource.hash_url(url),
            host="calendar.google.com",
            **fields,
        )

    def add(self, url=URL, name="", **extra):
        return self.client.post(
            reverse("calendar_sync:ics_add"), {"ics_url": url, "name": name}, **extra
        )


class AddCalendarTest(IcsViewsTestCase):
    def test_adding_a_calendar_imports_its_appointments(self):
        with patch(FETCH, return_value=future_feed()) as fetch:
            response = self.add(name="Mein Google")

        self.assertRedirects(
            response,
            reverse("core:settings") + "?section=calendar-sync",
            fetch_redirect_response=False,
        )
        fetch.assert_called_once_with(URL)
        source = IcsCalendarSource.objects.get(user=self.user)
        self.assertEqual((source.name, source.host), ("Mein Google", "calendar.google.com"))
        self.assertEqual(BlockedTime.objects.get(user=self.user).title, "Vorlesung")
        self.assertIn("1 appointments", " ".join(texts(response)))

    def test_the_address_is_stored_encrypted(self):
        with patch(FETCH, return_value=future_feed()):
            self.add()

        source = IcsCalendarSource.objects.get()
        self.assertNotIn(b"private-", bytes(source.encrypted_url))
        self.assertEqual(decrypt_password(bytes(source.encrypted_url)), URL)
        self.assertNotIn("private-", source.url_hash)

    def test_the_address_never_comes_back_in_messages_redirects_or_pages(self):
        with patch(FETCH, return_value=future_feed()):
            response = self.add(follow=True)

        self.assertNotIn(
            "private-0123", response.request["PATH_INFO"] + response.request["QUERY_STRING"]
        )
        self.assertNotIn("private-0123", response.content.decode())
        self.assertNotIn("private-0123", " ".join(texts(response)))
        page = self.client.get(reverse("core:settings"))
        self.assertNotIn("private-0123", page.content.decode())

    def test_the_name_defaults_and_is_shortened(self):
        with patch(FETCH, return_value=future_feed()):
            self.add(name="")
            self.add(url=URL.replace("0123", "7777"), name="x" * 300)

        names = list(IcsCalendarSource.objects.values_list("name", flat=True))
        self.assertEqual(names[0], "Google Calendar")
        self.assertEqual(len(names[1]), 100)

    def test_webcal_addresses_are_accepted(self):
        with patch(FETCH, return_value=future_feed()):
            self.add(url=URL.replace("https://", "webcal://"))

        self.assertEqual(IcsCalendarSource.objects.count(), 1)

    def test_other_hosts_are_refused_without_any_request(self):
        with patch(FETCH) as fetch:
            response = self.add(url="https://evil.example/calendar/ical/x/basic.ics")

        fetch.assert_not_called()
        self.assertFalse(IcsCalendarSource.objects.exists())
        self.assertIn("Google Calendar", " ".join(texts(response)))

    def test_an_empty_address_is_refused(self):
        with patch(FETCH) as fetch:
            response = self.add(url="   ")

        fetch.assert_not_called()
        self.assertFalse(IcsCalendarSource.objects.exists())
        self.assertTrue(texts(response))

    def test_the_same_calendar_cannot_be_added_twice(self):
        with patch(FETCH, return_value=future_feed()) as fetch:
            self.add()
            response = self.add()

        self.assertEqual(IcsCalendarSource.objects.count(), 1)
        self.assertEqual(fetch.call_count, 1)
        self.assertIn("already connected", " ".join(texts(response)))

    def test_the_same_address_for_two_tutors_is_fine(self):
        other = User.objects.create_user(username="other", password="pass")
        self.make_source(user=other)

        with patch(FETCH, return_value=future_feed()):
            self.add()

        self.assertEqual(IcsCalendarSource.objects.count(), 2)

    def test_at_most_five_calendars_per_tutor(self):
        for n in range(IcsCalendarSource.MAX_PER_USER):
            self.make_source(url=URL.replace("0123", f"{n:04d}"), name=f"Q{n}")

        with patch(FETCH) as fetch:
            response = self.add(url=URL.replace("0123", "8888"))

        fetch.assert_not_called()
        self.assertEqual(IcsCalendarSource.objects.count(), IcsCalendarSource.MAX_PER_USER)
        self.assertIn("up to 5", " ".join(texts(response)))

    def test_a_calendar_that_cannot_be_retrieved_is_not_saved(self):
        with patch(
            FETCH, side_effect=IcsError("fetch_failed", "The calendar server could not be reached.")
        ):
            response = self.add()

        self.assertFalse(IcsCalendarSource.objects.exists())
        self.assertIn("could not be retrieved", " ".join(texts(response)))

    def test_something_that_is_not_a_calendar_is_not_saved(self):
        with patch(FETCH, return_value=b"<html>Bitte anmelden</html>"):
            response = self.add()

        self.assertFalse(IcsCalendarSource.objects.exists())
        self.assertFalse(BlockedTime.objects.exists())
        self.assertIn("does not lead to a calendar", " ".join(texts(response)))

    def test_without_the_encryption_key_nothing_is_saved(self):
        with override_settings(CALDAV_ENCRYPTION_KEY=""), patch(FETCH, return_value=future_feed()):
            response = self.add()

        self.assertFalse(IcsCalendarSource.objects.exists())
        self.assertIn("not available right now", " ".join(texts(response)))

    def test_login_is_required(self):
        self.client.logout()

        with patch(FETCH) as fetch:
            response = self.add()

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
        fetch.assert_not_called()

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(reverse("calendar_sync:ics_add")).status_code, 405)


class ManageCalendarTest(IcsViewsTestCase):
    def setUp(self):
        super().setUp()
        self.other = User.objects.create_user(username="other", password="pass")

    def test_removing_a_calendar_removes_its_blocked_times_but_nothing_else(self):
        with patch(FETCH, return_value=future_feed()):
            self.add()
        source = IcsCalendarSource.objects.get()
        now = timezone.now()
        manual = BlockedTime.objects.create(
            user=self.user, title="Urlaub", start_datetime=now, end_datetime=now
        )
        foreign = BlockedTime.objects.create(
            user=self.other, title="Fremd", start_datetime=now, end_datetime=now
        )

        response = self.client.post(reverse("calendar_sync:ics_remove", args=[source.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(IcsCalendarSource.objects.exists())
        self.assertEqual(
            sorted(BlockedTime.objects.values_list("title", flat=True)), ["Fremd", "Urlaub"]
        )
        self.assertTrue(BlockedTime.objects.filter(pk=manual.pk).exists())
        self.assertTrue(BlockedTime.objects.filter(pk=foreign.pk).exists())

    def test_another_tutors_calendar_cannot_be_removed_paused_or_synced(self):
        theirs = self.make_source(user=self.other)

        for name in ("ics_remove", "ics_toggle", "ics_sync_now"):
            with self.subTest(aktion=name), patch(FETCH) as fetch:
                response = self.client.post(reverse(f"calendar_sync:{name}", args=[theirs.pk]))
                self.assertEqual(response.status_code, 404)
                fetch.assert_not_called()

        theirs.refresh_from_db()
        self.assertTrue(theirs.sync_enabled)

    def test_pausing_and_resuming(self):
        source = self.make_source()

        self.client.post(reverse("calendar_sync:ics_toggle", args=[source.pk]))
        source.refresh_from_db()
        self.assertFalse(source.sync_enabled)

        self.client.post(reverse("calendar_sync:ics_toggle", args=[source.pk]))
        source.refresh_from_db()
        self.assertTrue(source.sync_enabled)

    def test_sync_now_imports_and_reports_the_numbers(self):
        source = self.make_source()

        with patch("apps.calendar_sync.ics_sync.fetch_ics", return_value=future_feed()):
            response = self.client.post(reverse("calendar_sync:ics_sync_now", args=[source.pk]))

        self.assertEqual(BlockedTime.objects.count(), 1)
        self.assertIn("1 new", " ".join(texts(response)))

    def test_sync_now_waits_a_minute_between_clicks(self):
        source = self.make_source(last_attempt_at=timezone.now() - timedelta(seconds=20))

        with patch("apps.calendar_sync.ics_sync.fetch_ics") as fetch:
            response = self.client.post(reverse("calendar_sync:ics_sync_now", args=[source.pk]))

        fetch.assert_not_called()
        self.assertIn("wait a minute", " ".join(texts(response)))

    def test_sync_now_reports_an_error_without_the_address(self):
        source = self.make_source()

        with patch(
            "apps.calendar_sync.ics_sync.fetch_ics", side_effect=IcsError("fetch_failed", "x")
        ):
            response = self.client.post(reverse("calendar_sync:ics_sync_now", args=[source.pk]))

        source.refresh_from_db()
        self.assertEqual(source.last_sync_error, "fetch_failed")
        self.assertNotIn("private-", " ".join(texts(response)))

    def test_only_post_is_allowed(self):
        source = self.make_source()

        for name in ("ics_remove", "ics_toggle", "ics_sync_now"):
            with self.subTest(aktion=name):
                self.assertEqual(
                    self.client.get(reverse(f"calendar_sync:{name}", args=[source.pk])).status_code,
                    405,
                )


class SettingsPageTest(IcsViewsTestCase):
    def test_the_calendar_cards_are_shown_on_every_device(self):
        # Kein Apple-Gerät: früher blieb die Karte hier versteckt und ein Skript schaltete sie nur für Mac/iPhone frei.
        response = self.client.get(
            reverse("core:settings"), HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="calendar-sync" aria-labelledby="calendar-sync-title">', html)
        self.assertNotIn("CalDAV against iCloud is only relevant on Apple devices", html)
        self.assertIn('id="calendar-import"', html)
        self.assertIn('id="calendar-feed"', html)

    def test_a_connected_calendar_is_listed_by_name_and_host_only(self):
        self.make_source(name="Mein Google", last_synced_at=timezone.now())

        html = self.client.get(reverse("core:settings")).content.decode()

        self.assertIn("Mein Google", html)
        self.assertIn("calendar.google.com", html)
        self.assertNotIn("private-0123", html)
        self.assertNotIn("anna%40gmail.com", html)

    def test_an_error_is_shown_as_a_sentence_never_as_a_code(self):
        self.make_source(last_sync_error="fetch_failed")

        html = self.client.get(reverse("core:settings")).content.decode()

        self.assertIn("could not be retrieved", html)
        self.assertNotIn("fetch_failed", html)

    def test_the_add_form_goes_away_when_the_limit_is_reached(self):
        for n in range(IcsCalendarSource.MAX_PER_USER):
            self.make_source(url=URL.replace("0123", f"{n:04d}"), name=f"Q{n}")

        html = self.client.get(reverse("core:settings")).content.decode()

        self.assertNotIn('name="ics_url"', html)
        self.assertIn("up to 5 calendars", html)

    def test_the_add_form_hides_the_address_while_typing(self):
        html = self.client.get(reverse("core:settings")).content.decode()

        self.assertIn('type="password" name="ics_url"', html)

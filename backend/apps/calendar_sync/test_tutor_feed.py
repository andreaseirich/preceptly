"""Kalender-Abo für Tutoren: der öffentliche Abruf und das Verwalten des Links."""

import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from icalendar import Calendar

from apps.calendar_sync.models import TutorCalendarFeed
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Lesson

BERLIN = ZoneInfo("Europe/Berlin")


def today():
    return datetime.now(BERLIN).date()


def make_contract(user, first="Max", last="Muster"):
    return Contract.objects.create(
        user=user,
        first_name=first,
        last_name=last,
        hourly_rate=Decimal("20.00"),
        start_date=today(),
    )


def make_lesson(contract, days, status="planned", start=time(14, 0), minutes=60, **extra):
    return Lesson.objects.create(
        contract=contract,
        date=today() + timedelta(days=days),
        start_time=start,
        duration_minutes=minutes,
        status=status,
        **extra,
    )


class FeedTestCase(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="pass")
        self.contract = make_contract(self.tutor)
        self.feed = TutorCalendarFeed.objects.create(user=self.tutor)
        self.client.defaults["HTTP_ACCEPT_LANGUAGE"] = "en"

    def url(self, token=None):
        return reverse("calendar_sync:tutor_feed", args=[token or self.feed.token])

    def events(self, token=None):
        response = self.client.get(self.url(token))
        self.assertEqual(response.status_code, 200)
        return list(Calendar.from_ical(response.content).walk("VEVENT"))


class FeedContentTest(FeedTestCase):
    def test_the_lessons_of_the_tutor_are_in_the_feed(self):
        make_lesson(self.contract, 1, "planned")
        make_lesson(self.contract, -1, "taught")
        make_lesson(self.contract, -3, "paid")

        events = self.events()

        self.assertEqual(len(events), 3)

    def test_cancelled_lessons_and_lessons_outside_the_window_are_left_out(self):
        make_lesson(self.contract, 1, "cancelled")
        make_lesson(self.contract, -60, "taught")
        make_lesson(self.contract, 400, "planned")
        keep = make_lesson(self.contract, 2, "planned")

        events = self.events()

        self.assertEqual(
            [str(e["uid"]) for e in events], [f"preceptly-tutor-session-{keep.pk}@preceptly.de"]
        )

    def test_other_tutors_lessons_never_appear(self):
        other = User.objects.create_user(username="other", password="pass")
        make_lesson(make_contract(other, "Fremd", "Schüler"), 1)
        mine = make_lesson(self.contract, 1)

        events = self.events()

        self.assertEqual(len(events), 1)
        self.assertIn(str(mine.pk), str(events[0]["uid"]))

    def test_titles_are_neutral_by_default(self):
        make_lesson(self.contract, 1)

        response = self.client.get(self.url())

        self.assertNotIn(b"Muster", response.content)
        self.assertEqual(str(self.events()[0]["summary"]), "Nachhilfe")

    def test_the_student_name_only_appears_when_the_tutor_switched_it_on(self):
        make_lesson(self.contract, 1)
        TutorCalendarFeed.objects.filter(pk=self.feed.pk).update(include_student_names=True)

        self.assertEqual(str(self.events()[0]["summary"]), "Nachhilfe - Max Muster")

    def test_times_are_in_the_tutors_time_zone(self):
        make_lesson(self.contract, 1, start=time(14, 0), minutes=45)

        event = self.events()[0]

        start = event["dtstart"].dt
        self.assertEqual(
            start, datetime.combine(today() + timedelta(days=1), time(14, 0), tzinfo=BERLIN)
        )
        self.assertEqual(event["dtend"].dt - start, timedelta(minutes=45))

    def test_a_tutor_in_another_time_zone_gets_local_times(self):
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"timezone": "America/New_York"}
        )
        make_lesson(self.contract, 1, start=time(14, 0))

        start = self.events()[0]["dtstart"].dt

        expected = datetime.combine(
            today() + timedelta(days=1), time(14, 0), tzinfo=ZoneInfo("America/New_York")
        )
        self.assertEqual(start, expected)

    def test_only_title_and_time_are_shared(self):
        make_lesson(
            self.contract,
            1,
            notes="Geheime Notiz",
            homework="Geheime Hausaufgabe",
            meeting_url="https://meet.example/geheim",
            travel_time_before_minutes=30,
        )

        response = self.client.get(self.url())

        for secret in (
            b"Geheime",
            b"meet.example",
            b"Muster",
            b"DESCRIPTION",
            b"LOCATION",
            b"ATTENDEE",
        ):
            with self.subTest(inhalt=secret):
                self.assertNotIn(secret, response.content)

    def test_travel_time_is_not_part_of_the_appointment(self):
        make_lesson(
            self.contract,
            1,
            start=time(14, 0),
            minutes=60,
            travel_time_before_minutes=30,
            travel_time_after_minutes=30,
        )

        event = self.events()[0]

        self.assertEqual(event["dtend"].dt - event["dtstart"].dt, timedelta(minutes=60))
        self.assertEqual(event["dtstart"].dt.hour, 14)

    def test_the_uid_marks_the_appointment_as_preceptlys_own(self):
        # Daran erkennt der Import einer Kalenderadresse die eigenen Stunden und überspringt sie.
        make_lesson(self.contract, 1)

        self.assertTrue(str(self.events()[0]["uid"]).endswith("@preceptly.de"))

    def test_the_calendar_asks_to_be_refreshed_hourly(self):
        response = self.client.get(self.url())

        body = response.content.decode()
        self.assertIn("X-WR-CALNAME:Preceptly Nachhilfe", body)
        self.assertIn("REFRESH-INTERVAL;VALUE=DURATION:PT1H", body)
        self.assertIn("X-PUBLISHED-TTL:PT1H", body)

    def test_an_empty_feed_is_a_valid_calendar(self):
        self.assertEqual(self.events(), [])


class FeedAccessTest(FeedTestCase):
    def test_no_login_is_needed_the_token_is_the_key(self):
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_the_response_is_a_private_calendar_file(self):
        response = self.client.get(self.url())

        self.assertEqual(response["Content-Type"], "text/calendar; charset=utf-8")
        self.assertEqual(response["Cache-Control"], "private, max-age=300")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertIn("preceptly.ics", response["Content-Disposition"])

    def test_an_unknown_token_is_not_found(self):
        self.assertEqual(self.client.get(self.url(uuid.uuid4())).status_code, 404)

    def test_a_deactivated_account_has_no_feed(self):
        User.objects.filter(pk=self.tutor.pk).update(is_active=False)

        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_only_reading_is_allowed(self):
        self.assertEqual(self.client.post(self.url()).status_code, 405)
        self.assertEqual(self.client.head(self.url()).status_code, 200)

    def test_the_last_retrieval_is_recorded_but_not_on_every_call(self):
        self.client.get(self.url())
        self.feed.refresh_from_db()
        first = self.feed.last_fetched_at
        self.assertIsNotNone(first)

        self.client.get(self.url())
        self.feed.refresh_from_db()

        self.assertEqual(self.feed.last_fetched_at, first)

    def test_the_token_is_not_the_account_or_a_counter(self):
        other = TutorCalendarFeed.objects.create(
            user=User.objects.create_user(username="b", password="pass")
        )

        self.assertNotEqual(self.feed.token, other.token)
        self.assertEqual(self.feed.token.version, 4)


class ManageFeedTest(FeedTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="tutor", password="pass")

    def test_switching_on_creates_the_link_once(self):
        TutorCalendarFeed.objects.all().delete()

        self.client.post(reverse("calendar_sync:feed_enable"))
        first = TutorCalendarFeed.objects.get(user=self.tutor).token
        self.client.post(reverse("calendar_sync:feed_enable"))

        self.assertEqual(TutorCalendarFeed.objects.get(user=self.tutor).token, first)
        self.assertFalse(TutorCalendarFeed.objects.get(user=self.tutor).include_student_names)

    def test_a_new_link_makes_the_old_one_useless_immediately(self):
        old = self.feed.token

        response = self.client.post(reverse("calendar_sync:feed_renew"))

        self.assertEqual(response.status_code, 302)
        self.feed.refresh_from_db()
        self.assertNotEqual(self.feed.token, old)
        self.assertEqual(self.client.get(self.url(old)).status_code, 404)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_renewing_resets_the_last_retrieval(self):
        self.client.get(self.url())

        self.client.post(reverse("calendar_sync:feed_renew"))

        self.feed.refresh_from_db()
        self.assertIsNone(self.feed.last_fetched_at)

    def test_switching_off_kills_the_link(self):
        token = self.feed.token

        self.client.post(reverse("calendar_sync:feed_disable"))

        self.assertFalse(TutorCalendarFeed.objects.exists())
        self.assertEqual(self.client.get(self.url(token)).status_code, 404)

    def test_the_student_name_option_can_be_switched_on_and_off(self):
        self.client.post(reverse("calendar_sync:feed_names"), {"include_student_names": "on"})
        self.feed.refresh_from_db()
        self.assertTrue(self.feed.include_student_names)

        self.client.post(reverse("calendar_sync:feed_names"), {})
        self.feed.refresh_from_db()
        self.assertFalse(self.feed.include_student_names)

    def test_one_tutor_cannot_touch_another_tutors_link(self):
        other = User.objects.create_user(username="other", password="pass")
        theirs = TutorCalendarFeed.objects.create(user=other)
        token = theirs.token

        self.client.post(reverse("calendar_sync:feed_renew"))
        self.client.post(reverse("calendar_sync:feed_disable"))
        self.client.post(reverse("calendar_sync:feed_names"), {"include_student_names": "on"})

        theirs.refresh_from_db()
        self.assertEqual(theirs.token, token)
        self.assertFalse(theirs.include_student_names)

    def test_login_is_required_for_managing(self):
        self.client.logout()

        for name in ("feed_enable", "feed_renew", "feed_disable", "feed_names"):
            with self.subTest(aktion=name):
                response = self.client.post(reverse(f"calendar_sync:{name}"))
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response["Location"])
        self.assertTrue(TutorCalendarFeed.objects.filter(pk=self.feed.pk).exists())

    def test_managing_needs_post(self):
        for name in ("feed_enable", "feed_renew", "feed_disable", "feed_names"):
            with self.subTest(aktion=name):
                self.assertEqual(self.client.get(reverse(f"calendar_sync:{name}")).status_code, 405)


class FeedOnSettingsPageTest(FeedTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="tutor", password="pass")

    def test_before_switching_on_there_is_a_button_and_no_link(self):
        TutorCalendarFeed.objects.all().delete()

        html = self.client.get(reverse("core:settings")).content.decode()

        self.assertIn(reverse("calendar_sync:feed_enable"), html)
        self.assertNotIn("tutor-feed-url-input", html)

    def test_after_switching_on_the_link_and_a_webcal_variant_are_shown(self):
        html = self.client.get(reverse("core:settings")).content.decode()

        self.assertIn(f"/calendar-sync/feed/{self.feed.token}.ics", html)
        self.assertIn(f"webcal://testserver/calendar-sync/feed/{self.feed.token}.ics", html)
        self.assertIn('data-copy-from="tutor-feed-url-input"', html)
        self.assertIn(reverse("calendar_sync:feed_renew"), html)

    def test_the_link_is_only_shown_to_its_owner(self):
        other = User.objects.create_user(username="other", password="pass")
        self.client.logout()
        self.client.login(username="other", password="pass")

        html = self.client.get(reverse("core:settings")).content.decode()

        self.assertNotIn(str(self.feed.token), html)
        self.assertFalse(
            TutorCalendarFeed.objects.filter(user=other).exists()
        )  # und es wurde keiner angelegt

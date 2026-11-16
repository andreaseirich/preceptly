"""Kalender per Adresse einbinden (Google "geheime Adresse im iCal-Format"): Abruf und Auswertung.

Freigabe von Andreas am 10.11.2026 ("Ja, mach das so"): Blockzeiten aus Google Kalender ohne OAuth.
Geprüft werden die Abwehr gegen missbrauchte Adressen (SSRF), der Abruf ohne Netz (ersetzte Funktionen) und die Auswertung
mit wiederkehrenden Terminen, Zeitzonen und ganztägigen Terminen.
"""

import unittest
from datetime import datetime, timedelta
from datetime import timezone as tz

import requests

from apps.calendar_sync.ics_import import (
    MAX_BYTES,
    IcsError,
    Occurrence,
    default_window,
    fetch_ics,
    normalize_ics_url,
    parse_occurrences,
)

GOOD = "https://calendar.google.com/calendar/ical/anna%40gmail.com/private-0123456789abcdef0123/basic.ics"
UTC = tz.utc
WINDOW = (datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 12, 1, tzinfo=UTC))


def PUBLIC(host):  # noqa: N802
    return ["142.250.185.78"]


def ics(*events, header=""):
    body = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Google Inc//Google Calendar 70.9054//EN",
            header,
            *events,
            "END:VCALENDAR",
            "",
        ]
    )
    return body.replace("\r\n\r\n", "\r\n").encode()


def event(*lines):
    return "\r\n".join(["BEGIN:VEVENT", *lines, "END:VEVENT"])


class NormalizeUrlTest(unittest.TestCase):
    def code(self, value):
        with self.assertRaises(IcsError) as caught:
            normalize_ics_url(value)
        return caught.exception.code

    def test_the_google_address_is_accepted_unchanged(self):
        self.assertEqual(normalize_ics_url(GOOD), GOOD)

    def test_webcal_becomes_https_and_spaces_around_are_ignored(self):
        self.assertEqual(
            normalize_ics_url("  " + GOOD.replace("https://", "webcal://") + "\n"), GOOD
        )
        self.assertEqual(normalize_ics_url(GOOD.replace("https://", "webcals://")), GOOD)

    def test_the_host_is_compared_in_lower_case_and_the_fragment_is_dropped(self):
        self.assertEqual(
            normalize_ics_url(GOOD.replace("calendar.google.com", "CALENDAR.Google.COM") + "#x"),
            GOOD,
        )

    def test_empty_input(self):
        for value in ("", "   ", None):
            with self.subTest(wert=value):
                self.assertEqual(self.code(value), "empty")

    def test_only_https_is_allowed(self):
        for scheme in ("http://", "ftp://", "file://", "javascript:", "data:"):
            with self.subTest(schema=scheme):
                self.assertEqual(self.code(GOOD.replace("https://", scheme)), "bad_url")

    def test_other_hosts_are_refused(self):
        for value in (
            "https://evil.example/calendar/ical/x/basic.ics",
            "https://calendar.google.com.evil.example/calendar/ical/x/basic.ics",
            "https://evilcalendar.google.com/calendar/ical/x/basic.ics",
            "https://www.google.com/calendar/ical/x/basic.ics",
            "https://142.250.185.78/calendar/ical/x/basic.ics",
            "https://localhost/calendar/ical/x/basic.ics",
            "https://169.254.169.254/latest/meta-data/",
            "https://calendаr.google.com/calendar/ical/x/basic.ics",  # kyrillisches "а"
        ):
            with self.subTest(adresse=value):
                self.assertEqual(self.code(value), "host_not_allowed")

    def test_credentials_in_the_address_are_refused(self):
        for value in (
            "https://calendar.google.com@evil.example/calendar/ical/x/basic.ics",
            "https://evil.example@calendar.google.com/calendar/ical/x/basic.ics",
            "https://user:pass@calendar.google.com/calendar/ical/x/basic.ics",
            "https://evil.example\\@calendar.google.com/calendar/ical/x/basic.ics",
        ):
            with self.subTest(adresse=value):
                self.assertEqual(self.code(value), "bad_url")

    def test_other_ports_are_refused(self):
        for port in (80, 8443, 22, 6379):
            with self.subTest(port=port):
                self.assertEqual(
                    self.code(GOOD.replace("calendar.google.com", f"calendar.google.com:{port}")),
                    "bad_url",
                )
        self.assertEqual(
            normalize_ics_url(GOOD.replace("calendar.google.com", "calendar.google.com:443")), GOOD
        )

    def test_only_the_calendar_path_of_the_host_is_allowed(self):
        for path in (
            "/",
            "/calendar/ical",
            "/calendar/render",
            "/other/calendar/ical/x/basic.ics",
            "/calendar/../admin",
        ):
            with self.subTest(pfad=path):
                self.assertEqual(
                    self.code("https://calendar.google.com" + path), "host_not_allowed"
                )

    def test_control_characters_and_inner_spaces_are_refused(self):
        for value in (GOOD + "\r\nX-Header: 1", GOOD.replace("basic", "ba sic"), GOOD + "\x00"):
            with self.subTest(wert=repr(value)[-20:]):
                self.assertEqual(self.code(value), "bad_url")

    def test_a_very_long_address_is_refused(self):
        self.assertEqual(self.code(GOOD + "a" * 3000), "bad_url")


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None, chunks=None):
        self.status_code = status
        self.headers = headers or {}
        self._chunks = chunks if chunks is not None else [body]
        self.closed = False

    def iter_content(self, size):
        yield from self._chunks

    def close(self):
        self.closed = True


class FetchTest(unittest.TestCase):
    def fetch(self, responses, resolve=PUBLIC, url=GOOD):
        calls = []
        queue = list(responses)

        def get(called_url, **kwargs):
            calls.append((called_url, kwargs))
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        result = fetch_ics(url, get=get, resolve=resolve)
        return result, calls

    def error(self, responses, **kwargs):
        with self.assertRaises(IcsError) as caught:
            self.fetch(responses, **kwargs)
        return caught.exception

    def test_a_normal_answer_returns_the_content(self):
        body, calls = self.fetch([FakeResponse(body=b"BEGIN:VCALENDAR")])

        self.assertEqual(body, b"BEGIN:VCALENDAR")
        url, kwargs = calls[0]
        self.assertEqual(url, GOOD)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])
        self.assertEqual(kwargs["timeout"], (5, 15))
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertNotIn("Cookie", kwargs["headers"])

    def test_the_response_is_always_closed(self):
        response = FakeResponse(body=b"x")

        self.fetch([response])

        self.assertTrue(response.closed)

    def test_names_that_point_to_internal_addresses_are_refused(self):
        for address in (
            "10.0.0.5",
            "127.0.0.1",
            "169.254.169.254",
            "192.168.1.1",
            "100.64.0.7",
            "172.16.0.1",
            "::1",
            "fd00::1",
            "fe80::1",
            "0.0.0.0",
            "224.0.0.1",
        ):
            with self.subTest(adresse=address):
                error = self.error([FakeResponse(body=b"x")], resolve=lambda host, a=address: [a])
                self.assertEqual(error.code, "host_not_allowed")

    def test_one_internal_address_among_public_ones_is_enough_to_refuse(self):
        error = self.error(
            [FakeResponse(body=b"x")], resolve=lambda host: ["142.250.185.78", "10.0.0.5"]
        )

        self.assertEqual(error.code, "host_not_allowed")

    def test_an_unresolvable_name_is_a_fetch_error(self):
        self.assertEqual(
            self.error([FakeResponse(body=b"x")], resolve=lambda host: []).code, "fetch_failed"
        )

    def test_a_redirect_to_an_allowed_address_is_followed(self):
        target = "https://calendar.google.com/calendar/ical/other/basic.ics"

        body, calls = self.fetch(
            [FakeResponse(302, headers={"Location": target}), FakeResponse(body=b"OK")]
        )

        self.assertEqual(body, b"OK")
        self.assertEqual(calls[1][0], target)

    def test_a_relative_redirect_stays_on_the_host(self):
        body, calls = self.fetch(
            [
                FakeResponse(301, headers={"Location": "/calendar/ical/other/basic.ics"}),
                FakeResponse(body=b"OK"),
            ]
        )

        self.assertEqual(calls[1][0], "https://calendar.google.com/calendar/ical/other/basic.ics")

    def test_a_redirect_to_another_host_is_refused(self):
        for target in (
            "https://evil.example/calendar/ical/x/basic.ics",
            "http://calendar.google.com/calendar/ical/x",
            "https://169.254.169.254/",
            "https://calendar.google.com/accounts/login",
        ):
            with self.subTest(ziel=target):
                error = self.error([FakeResponse(302, headers={"Location": target})])
                self.assertIn(error.code, ("host_not_allowed", "bad_url"))

    def test_redirect_loops_end(self):
        loop = [FakeResponse(302, headers={"Location": GOOD}) for _ in range(10)]

        error = self.error(loop)

        self.assertEqual(error.code, "fetch_failed")

    def test_a_missing_address_is_reported_with_the_status_but_without_the_address(self):
        error = self.error([FakeResponse(404)])

        self.assertEqual(error.code, "fetch_failed")
        self.assertIn("404", str(error))
        self.assertNotIn("private-0123456789abcdef0123", str(error))

    def test_network_errors_never_carry_the_address(self):
        boom = requests.ConnectionError(
            f"HTTPSConnectionPool: Max retries exceeded with url: {GOOD}"
        )

        error = self.error([boom])

        self.assertEqual(error.code, "fetch_failed")
        self.assertNotIn("private-0123456789abcdef0123", str(error))
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)

    def test_a_too_large_file_is_cut_off(self):
        chunks = [b"x" * (1024 * 1024)] * 7

        error = self.error([FakeResponse(chunks=chunks)])

        self.assertEqual(error.code, "too_large")
        self.assertEqual(MAX_BYTES, 5 * 1024 * 1024)

    def test_a_forbidden_address_is_refused_before_any_request(self):
        calls = []
        with self.assertRaises(IcsError):
            fetch_ics(
                "https://evil.example/calendar/ical/x",
                get=lambda *a, **k: calls.append(a),
                resolve=PUBLIC,
            )

        self.assertEqual(calls, [])


class ParseTest(unittest.TestCase):
    def parse(self, *events, header="X-WR-TIMEZONE:Europe/Berlin", window=WINDOW):
        return parse_occurrences(ics(*events, header=header), *window)

    def test_a_simple_event_with_a_time_zone(self):
        [item] = self.parse(
            event(
                "UID:a1@google.com",
                "DTSTART;TZID=Europe/Berlin:20261110T140000",
                "DTEND;TZID=Europe/Berlin:20261110T150000",
                "SUMMARY:Zahnarzt",
            )
        )

        self.assertEqual(item.summary, "Zahnarzt")
        self.assertEqual(item.start, datetime(2026, 11, 10, 13, 0, tzinfo=UTC))  # Winterzeit: UTC+1
        self.assertEqual(item.end, datetime(2026, 11, 10, 14, 0, tzinfo=UTC))
        self.assertFalse(item.all_day)
        self.assertEqual(item.uid, "a1@google.com")
        self.assertEqual(item.key, "a1@google.com|20261110T130000Z")

    def test_summer_time_is_applied(self):
        [item] = self.parse(
            event(
                "UID:s1",
                "DTSTART;TZID=Europe/Berlin:20260715T140000",
                "DTEND;TZID=Europe/Berlin:20260715T150000",
                "SUMMARY:Sommer",
            ),
            window=(datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC)),
        )

        self.assertEqual(item.start, datetime(2026, 7, 15, 12, 0, tzinfo=UTC))  # UTC+2

    def test_times_in_utc_and_without_zone(self):
        in_utc, floating = self.parse(
            event("UID:u1", "DTSTART:20261112T100000Z", "DTEND:20261112T110000Z", "SUMMARY:UTC"),
            event(
                "UID:f1", "DTSTART:20261113T100000", "DTEND:20261113T110000", "SUMMARY:Ohne Zone"
            ),
        )

        self.assertEqual(in_utc.start, datetime(2026, 11, 12, 10, 0, tzinfo=UTC))
        self.assertEqual(
            floating.start, datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
        )  # als Ortszeit gelesen

    def test_times_without_zone_and_without_calendar_zone_count_as_local_time(self):
        # Ohne X-WR-TIMEZONE bleibt die Zeit "schwebend"; dann greift unser Rückfall auf Europe/Berlin.
        [item] = self.parse(
            event(
                "UID:f2", "DTSTART:20261113T100000", "DTEND:20261113T110000", "SUMMARY:Schwebend"
            ),
            header="",
        )

        self.assertEqual(item.start, datetime(2026, 11, 13, 9, 0, tzinfo=UTC))
        self.assertEqual(item.end, datetime(2026, 11, 13, 10, 0, tzinfo=UTC))

    def test_the_zone_of_the_calendar_wins_over_the_fallback(self):
        # Steht im Kalender X-WR-TIMEZONE, gilt diese Zone für schwebende Zeiten (hier New York, UTC-5).
        [item] = self.parse(
            event(
                "UID:f3", "DTSTART:20261113T100000", "DTEND:20261113T110000", "SUMMARY:Andere Zone"
            ),
            header="X-WR-TIMEZONE:America/New_York",
        )

        self.assertEqual(item.start, datetime(2026, 11, 13, 15, 0, tzinfo=UTC))

    def test_all_day_events_without_calendar_zone_use_local_midnight(self):
        [item] = self.parse(
            event(
                "UID:d2",
                "DTSTART;VALUE=DATE:20261120",
                "DTEND;VALUE=DATE:20261121",
                "SUMMARY:Ganztags",
            ),
            header="",
        )

        self.assertEqual(item.start, datetime(2026, 11, 19, 23, 0, tzinfo=UTC))
        self.assertEqual(item.end, datetime(2026, 11, 20, 23, 0, tzinfo=UTC))

    def test_all_day_events_block_from_midnight_to_midnight_local_time(self):
        [item] = self.parse(
            event(
                "UID:d1",
                "DTSTART;VALUE=DATE:20261120",
                "DTEND;VALUE=DATE:20261122",
                "SUMMARY:Urlaub",
            )
        )

        self.assertTrue(item.all_day)
        self.assertEqual(
            item.start, datetime(2026, 11, 19, 23, 0, tzinfo=UTC)
        )  # 20.11. 00:00 Ortszeit
        self.assertEqual(
            item.end, datetime(2026, 11, 21, 23, 0, tzinfo=UTC)
        )  # DTEND ist exklusiv: bis 22.11. 00:00

    def test_a_duration_instead_of_an_end(self):
        [item] = self.parse(
            event(
                "UID:du1",
                "DTSTART;TZID=Europe/Berlin:20261110T100000",
                "DURATION:PT90M",
                "SUMMARY:Dauer",
            )
        )

        self.assertEqual(item.end - item.start, timedelta(minutes=90))

    def test_weekly_events_are_expanded_with_exceptions_and_moved_dates(self):
        items = self.parse(
            event(
                "UID:w1@google.com",
                "DTSTART;TZID=Europe/Berlin:20261006T180000",
                "DTEND;TZID=Europe/Berlin:20261006T190000",
                "RRULE:FREQ=WEEKLY;BYDAY=TU",
                "EXDATE;TZID=Europe/Berlin:20261117T180000",
                "SUMMARY:Chor",
            ),
            event(
                "UID:w1@google.com",
                "RECURRENCE-ID;TZID=Europe/Berlin:20261124T180000",
                "DTSTART;TZID=Europe/Berlin:20261124T190000",
                "DTEND;TZID=Europe/Berlin:20261124T200000",
                "SUMMARY:Chor (später)",
            ),
        )

        self.assertEqual(
            [
                (i.start.astimezone(tz(timedelta(hours=1))).strftime("%d.%m. %H:%M"), i.summary)
                for i in items
            ],
            [("03.11. 18:00", "Chor"), ("10.11. 18:00", "Chor"), ("24.11. 19:00", "Chor (später)")],
        )
        self.assertEqual(len({i.key for i in items}), 3)  # jeder Tag hat eine eigene Kennung

    def test_a_series_that_started_long_ago_still_blocks_today(self):
        items = self.parse(
            event(
                "UID:old",
                "DTSTART;TZID=Europe/Berlin:20240102T180000",
                "DTEND;TZID=Europe/Berlin:20240102T190000",
                "RRULE:FREQ=WEEKLY;BYDAY=TU",
                "SUMMARY:Alt",
            )
        )

        self.assertEqual(len(items), 4)  # vier Dienstage im November 2026

    def test_a_series_with_an_end_stops(self):
        items = self.parse(
            event(
                "UID:e",
                "DTSTART;TZID=Europe/Berlin:20261103T180000",
                "DTEND;TZID=Europe/Berlin:20261103T190000",
                "RRULE:FREQ=WEEKLY;COUNT=2",
                "SUMMARY:Kurs",
            )
        )

        self.assertEqual(len(items), 2)

    def test_events_outside_the_window_are_left_out(self):
        items = self.parse(
            event(
                "UID:v",
                "DTSTART;TZID=Europe/Berlin:20261020T100000",
                "DTEND;TZID=Europe/Berlin:20261020T110000",
                "SUMMARY:Vorher",
            ),
            event(
                "UID:n",
                "DTSTART;TZID=Europe/Berlin:20270105T100000",
                "DTEND;TZID=Europe/Berlin:20270105T110000",
                "SUMMARY:Nachher",
            ),
            event(
                "UID:i",
                "DTSTART;TZID=Europe/Berlin:20261105T100000",
                "DTEND;TZID=Europe/Berlin:20261105T110000",
                "SUMMARY:Drin",
            ),
        )

        self.assertEqual([i.summary for i in items], ["Drin"])

    def test_cancelled_and_free_events_do_not_block(self):
        items = self.parse(
            event(
                "UID:c",
                "DTSTART;TZID=Europe/Berlin:20261110T100000",
                "DTEND;TZID=Europe/Berlin:20261110T110000",
                "STATUS:CANCELLED",
                "SUMMARY:Abgesagt",
            ),
            event(
                "UID:t",
                "DTSTART;VALUE=DATE:20261111",
                "DTEND;VALUE=DATE:20261112",
                "TRANSP:TRANSPARENT",
                "SUMMARY:Geburtstag",
            ),
            event(
                "UID:o",
                "DTSTART;TZID=Europe/Berlin:20261112T100000",
                "DTEND;TZID=Europe/Berlin:20261112T110000",
                "TRANSP:OPAQUE",
                "SUMMARY:Zählt",
            ),
        )

        self.assertEqual([i.summary for i in items], ["Zählt"])

    def test_events_without_a_duration_are_skipped(self):
        items = self.parse(
            event(
                "UID:z",
                "DTSTART;TZID=Europe/Berlin:20261110T100000",
                "DTEND;TZID=Europe/Berlin:20261110T100000",
                "SUMMARY:Null",
            )
        )

        self.assertEqual(items, [])

    def test_summaries_are_cleaned_and_shortened(self):
        items = self.parse(
            event(
                "UID:s1",
                "DTSTART;TZID=Europe/Berlin:20261110T100000",
                "DTEND;TZID=Europe/Berlin:20261110T110000",
                "SUMMARY:  Viel   Platz\\nund Umbruch ",
            ),
            event(
                "UID:s2",
                "DTSTART;TZID=Europe/Berlin:20261111T100000",
                "DTEND;TZID=Europe/Berlin:20261111T110000",
                "SUMMARY:" + "x" * 500,
            ),
            event(
                "UID:s3",
                "DTSTART;TZID=Europe/Berlin:20261112T100000",
                "DTEND;TZID=Europe/Berlin:20261112T110000",
            ),
        )

        self.assertEqual(items[0].summary, "Viel Platz und Umbruch")
        self.assertEqual(len(items[1].summary), 200)
        self.assertEqual(items[2].summary, "Termin")

    def test_the_result_is_sorted_by_start(self):
        items = self.parse(
            event(
                "UID:b",
                "DTSTART;TZID=Europe/Berlin:20261120T100000",
                "DTEND;TZID=Europe/Berlin:20261120T110000",
                "SUMMARY:B",
            ),
            event(
                "UID:a",
                "DTSTART;TZID=Europe/Berlin:20261105T100000",
                "DTEND;TZID=Europe/Berlin:20261105T110000",
                "SUMMARY:A",
            ),
        )

        self.assertEqual([i.summary for i in items], ["A", "B"])

    def test_second_and_minute_series_are_ignored(self):
        items = self.parse(
            event(
                "UID:m",
                "DTSTART;TZID=Europe/Berlin:20261110T100000",
                "DTEND;TZID=Europe/Berlin:20261110T100100",
                "RRULE:FREQ=MINUTELY",
                "SUMMARY:Flut",
            ),
            event(
                "UID:ok",
                "DTSTART;TZID=Europe/Berlin:20261111T100000",
                "DTEND;TZID=Europe/Berlin:20261111T110000",
                "SUMMARY:Normal",
            ),
        )

        self.assertEqual([i.summary for i in items], ["Normal"])

    def test_too_many_appointments_are_refused_instead_of_cut_off(self):
        events = [
            event(
                f"UID:e{n}",
                f"DTSTART;TZID=Europe/Berlin:20261110T{n % 10:02d}0000",
                f"DTEND;TZID=Europe/Berlin:20261110T{n % 10:02d}3000",
                "SUMMARY:x",
            )
            for n in range(6)
        ]
        # gleiche Uhrzeiten, aber verschiedene Kennungen: sechs Termine
        with self.assertRaises(IcsError) as caught:
            parse_occurrences(ics(*events), *WINDOW, max_occurrences=5)

        self.assertEqual(caught.exception.code, "too_many_events")

    def test_files_that_are_not_calendars(self):
        for data in (
            b"",
            b"garbage",
            b"<html>login</html>",
            b"BEGIN:VEVENT\r\nEND:VEVENT\r\n",
            "ä".encode(),
        ):
            with self.subTest(daten=data[:20]):
                with self.assertRaises(IcsError) as caught:
                    parse_occurrences(data, *WINDOW)
                self.assertEqual(caught.exception.code, "not_ical")

    def test_a_calendar_without_events_is_fine(self):
        self.assertEqual(self.parse(), [])

    def test_the_same_event_twice_counts_once(self):
        one = event(
            "UID:d",
            "DTSTART;TZID=Europe/Berlin:20261110T100000",
            "DTEND;TZID=Europe/Berlin:20261110T110000",
            "SUMMARY:Doppelt",
        )

        self.assertEqual(len(self.parse(one, one)), 1)

    def test_occurrence_is_a_value_object(self):
        [item] = self.parse(
            event(
                "UID:v",
                "DTSTART;TZID=Europe/Berlin:20261110T100000",
                "DTEND;TZID=Europe/Berlin:20261110T110000",
                "SUMMARY:V",
            )
        )

        self.assertIsInstance(item, Occurrence)
        with self.assertRaises(Exception):  # noqa: B017 (FrozenInstanceError)
            item.summary = "anders"


class DefaultWindowTest(unittest.TestCase):
    def test_seven_days_back_and_180_ahead(self):
        now = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)

        start, end = default_window(now)

        self.assertEqual(start, now - timedelta(days=7))
        self.assertEqual(end, now + timedelta(days=180))


if __name__ == "__main__":
    unittest.main()

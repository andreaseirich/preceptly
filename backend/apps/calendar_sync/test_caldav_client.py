"""
Tests for caldav_client's all-day event normalization - the reason some
blocked times silently didn't block booking on their boundary day (a
naive date coerced to a bare UTC midnight by Django instead of a proper
local-timezone-aware datetime).
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from caldav.lib.error import NotFoundError, ReportError
from django.test import TestCase
from django.utils import timezone

from apps.calendar_sync.caldav_client import (
    CalDavClient,
    CalDavConnectionError,
    _normalize_event_dt,
)


class NormalizeEventDtTest(TestCase):
    def test_datetime_passed_through_unchanged(self):
        aware = timezone.make_aware(datetime(2026, 9, 10, 14, 0))
        self.assertEqual(_normalize_event_dt(aware), aware)

    def test_date_only_converted_to_local_midnight_aware(self):
        result = _normalize_event_dt(date(2026, 10, 30))
        self.assertTrue(timezone.is_aware(result))
        local = timezone.localtime(result)
        self.assertEqual(local.date(), date(2026, 10, 30))
        self.assertEqual(local.time(), datetime.min.time())

    def test_none_passed_through(self):
        self.assertIsNone(_normalize_event_dt(None))


class StaleUidReportErrorTest(TestCase):
    """iCloud sometimes answers a calendar-query for a UID that no longer
    exists with 412 Precondition Failed instead of an empty result/404 -
    observed in production trying to clean up a pushed Session's copy
    after the Session itself was deleted. get_event/delete_event must
    treat that the same as "not found", not raise."""

    def _client(self):
        # Bypass __init__'s real CalDAV handshake entirely.
        return CalDavClient.__new__(CalDavClient)

    def test_get_event_returns_none_on_412_report_error(self):
        client = self._client()
        mock_calendar = MagicMock()
        mock_calendar.event_by_uid.side_effect = ReportError(
            url="412 Precondition Failed\n\n", reason=None
        )
        with patch.object(CalDavClient, "_calendar", return_value=mock_calendar):
            result = client.get_event("https://caldav.icloud.com/cal/", "stale-uid")
        self.assertIsNone(result)

    def test_get_event_still_raises_on_other_report_errors(self):
        client = self._client()
        mock_calendar = MagicMock()
        mock_calendar.event_by_uid.side_effect = ReportError(
            url="500 Internal Server Error", reason=None
        )
        with patch.object(CalDavClient, "_calendar", return_value=mock_calendar):
            with self.assertRaises(CalDavConnectionError):
                client.get_event("https://caldav.icloud.com/cal/", "some-uid")

    def test_delete_event_is_a_no_op_on_412_report_error(self):
        client = self._client()
        mock_calendar = MagicMock()
        mock_calendar.event_by_uid.side_effect = ReportError(
            url="412 Precondition Failed\n\n", reason=None
        )
        with patch.object(CalDavClient, "_calendar", return_value=mock_calendar):
            client.delete_event("https://caldav.icloud.com/cal/", "stale-uid")  # must not raise

    def test_get_event_still_returns_none_on_plain_not_found(self):
        client = self._client()
        mock_calendar = MagicMock()
        mock_calendar.event_by_uid.side_effect = NotFoundError()
        with patch.object(CalDavClient, "_calendar", return_value=mock_calendar):
            result = client.get_event("https://caldav.icloud.com/cal/", "missing-uid")
        self.assertIsNone(result)

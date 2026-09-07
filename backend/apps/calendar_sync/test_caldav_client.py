"""
Tests for caldav_client's all-day event normalization - the reason some
blocked times silently didn't block booking on their boundary day (a
naive date coerced to a bare UTC midnight by Django instead of a proper
local-timezone-aware datetime).
"""

from datetime import date, datetime

from django.test import TestCase
from django.utils import timezone

from apps.calendar_sync.caldav_client import _normalize_event_dt


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

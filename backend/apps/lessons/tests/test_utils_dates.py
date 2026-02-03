"""
Tests for lessons/utils_dates.py - week start and add_days.
"""

from datetime import date

from apps.lessons.utils_dates import add_days_to_date, add_days_to_iso, get_week_start
from django.test import TestCase


class GetWeekStartTest(TestCase):
    """get_week_start returns Monday for any date."""

    def test_monday_returns_self(self):
        self.assertEqual(get_week_start(date(2025, 1, 6)), date(2025, 1, 6))

    def test_wednesday_returns_monday(self):
        self.assertEqual(get_week_start(date(2025, 1, 8)), date(2025, 1, 6))

    def test_sunday_returns_monday(self):
        self.assertEqual(get_week_start(date(2025, 1, 12)), date(2025, 1, 6))

    def test_year_boundary(self):
        self.assertEqual(get_week_start(date(2024, 12, 30)), date(2024, 12, 30))
        self.assertEqual(get_week_start(date(2025, 1, 1)), date(2024, 12, 30))


class AddDaysTest(TestCase):
    """add_days_to_date and add_days_to_iso."""

    def test_add_days_to_date(self):
        self.assertEqual(add_days_to_date(date(2025, 1, 6), 7), date(2025, 1, 13))
        self.assertEqual(add_days_to_date(date(2025, 1, 13), -7), date(2025, 1, 6))

    def test_add_days_to_iso(self):
        self.assertEqual(add_days_to_iso("2025-01-06", 7), "2025-01-13")
        self.assertEqual(add_days_to_iso("2025-01-13", -7), "2025-01-06")

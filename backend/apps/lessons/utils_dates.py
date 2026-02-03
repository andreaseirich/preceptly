"""
Date utilities for week handling. Monday-based weeks (ISO 8601).
"""

from datetime import date, timedelta


def get_week_start(target: date) -> date:
    """
    Return the Monday of the week containing target.

    Python weekday(): Monday=0, Sunday=6.
    """
    days_since_monday = target.weekday()
    return target - timedelta(days=days_since_monday)


def add_days_to_date(d: date, days: int) -> date:
    """Add days to a date; useful for week navigation (+/- 7)."""
    return d + timedelta(days=days)


def add_days_to_iso(iso_date: str, days: int) -> str:
    """Add days to an ISO date string (YYYY-MM-DD); returns ISO string."""
    d = date.fromisoformat(iso_date)
    return add_days_to_date(d, days).strftime("%Y-%m-%d")

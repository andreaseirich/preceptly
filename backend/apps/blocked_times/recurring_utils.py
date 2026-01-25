"""
Utility functions for finding recurring blocked times that match a blocked time.
"""

from datetime import date

from apps.blocked_times.models import BlockedTime
from apps.blocked_times.recurring_models import RecurringBlockedTime


def find_matching_recurring_blocked_time(blocked_time: BlockedTime) -> RecurringBlockedTime | None:
    """
    Finds the RecurringBlockedTime that a BlockedTime belongs to.

    A BlockedTime belongs to a RecurringBlockedTime if:
    - Same title
    - Same start and end time
    - The BlockedTime's date matches the RecurringBlockedTime's recurrence pattern
    """
    # Search for RecurringBlockedTimes with the same title and times
    recurring_blocked_times = RecurringBlockedTime.objects.filter(
        title=blocked_time.title,
        start_time=blocked_time.start_datetime.time(),
        end_time=blocked_time.end_datetime.time(),
        is_active=True,
    )

    for recurring in recurring_blocked_times:
        # Check if the BlockedTime's date matches the pattern
        matches = _date_matches_recurring_pattern(blocked_time.start_datetime.date(), recurring)
        if matches:
            return recurring

    return None


def get_all_blocked_times_for_recurring(
    recurring: RecurringBlockedTime, original_start_time=None
) -> list[BlockedTime]:
    """
    Finds all BlockedTimes that belong to a RecurringBlockedTime.

    This function finds BlockedTimes based on the recurrence pattern.
    If original_start_time is provided, it filters by that time
    (useful when the RecurringBlockedTime is being updated).
    """
    # Get all BlockedTimes in the series period
    all_blocked_times = BlockedTime.objects.filter(title=recurring.title)

    # Determine the period
    start_date = recurring.start_date
    end_date = recurring.end_date

    # Filter by date
    if end_date:
        all_blocked_times = all_blocked_times.filter(
            start_datetime__date__gte=start_date, start_datetime__date__lte=end_date
        )
    else:
        all_blocked_times = all_blocked_times.filter(start_datetime__date__gte=start_date)

    # Filter by start_time (if original_start_time is provided, use that, otherwise use current)
    start_time_to_match = (
        original_start_time if original_start_time is not None else recurring.start_time
    )
    all_blocked_times = all_blocked_times.filter(start_datetime__time=start_time_to_match)

    # Filter by weekday (based on active weekdays)
    recurring.get_active_weekdays()
    matching_blocked_times = []

    for blocked_time in all_blocked_times:
        if _date_matches_recurring_pattern(blocked_time.start_datetime.date(), recurring):
            matching_blocked_times.append(blocked_time)

    return matching_blocked_times


def _date_matches_recurring_pattern(blocked_date: date, recurring: RecurringBlockedTime) -> bool:
    """Checks if a date matches the recurrence pattern of a RecurringBlockedTime."""
    # Check if the date is within the period
    if blocked_date < recurring.start_date:
        return False

    if recurring.end_date and blocked_date > recurring.end_date:
        return False

    # Check if the weekday is active
    weekday = blocked_date.weekday()  # 0=Monday, 6=Sunday
    active_weekdays = recurring.get_active_weekdays()

    if weekday not in active_weekdays:
        return False

    # Check based on recurrence_type
    if recurring.recurrence_type == "weekly":
        # Every week - already checked by weekday
        return True

    elif recurring.recurrence_type == "biweekly":
        # Every 2 weeks
        weeks_since_start = (blocked_date - recurring.start_date).days // 7
        return weeks_since_start % 2 == 0

    elif recurring.recurrence_type == "monthly":
        # Monthly - same calendar day
        return blocked_date.day == recurring.start_date.day

    return False

"""
Utility functions for finding recurring sessions that match a session.
"""

from datetime import date

from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession


def find_matching_recurring_session(session: Session) -> RecurringSession | None:
    """
    Finds the RecurringSession that a session belongs to.

    A session belongs to a RecurringSession if:
    - Same contract
    - Same start time
    - The session's date matches the RecurringSession's recurrence pattern
    """
    # Search for RecurringSessions with the same contract and start time
    recurring_sessions = RecurringSession.objects.filter(
        contract=session.contract,
        start_time=session.start_time,
        is_active=True,
    )

    for recurring in recurring_sessions:
        # Check if the session's date matches the pattern
        matches = _date_matches_recurring_pattern(session.date, recurring)
        if matches:
            return recurring

    return None


# Alias for backwards compatibility
find_matching_recurring_lesson = find_matching_recurring_session


def get_all_sessions_for_recurring(
    recurring: RecurringSession, original_start_time=None
) -> list[Session]:
    """
    Finds all sessions that belong to a RecurringSession.

    This function finds sessions based on the recurrence pattern.
    If original_start_time is provided, it filters by that time
    (useful when the RecurringSession is being updated).
    """
    # Get all sessions for this contract in the series period
    all_sessions = Session.objects.filter(contract=recurring.contract)

    # Determine the period
    start_date = recurring.start_date
    end_date = recurring.end_date
    if not end_date and recurring.contract.end_date:
        end_date = recurring.contract.end_date

    # Filter by date
    if end_date:
        all_sessions = all_sessions.filter(date__gte=start_date, date__lte=end_date)
    else:
        all_sessions = all_sessions.filter(date__gte=start_date)

    # Filter by start_time (if original_start_time is provided, use that, otherwise use current)
    start_time_to_match = (
        original_start_time if original_start_time is not None else recurring.start_time
    )
    all_sessions = all_sessions.filter(start_time=start_time_to_match)

    # Filter by weekday (based on active weekdays)
    recurring.get_active_weekdays()
    matching_sessions = []

    for session in all_sessions:
        if _date_matches_recurring_pattern(session.date, recurring):
            matching_sessions.append(session)

    return matching_sessions


# Alias for backwards compatibility
get_all_lessons_for_recurring = get_all_sessions_for_recurring


def _date_matches_recurring_pattern(session_date: date, recurring: RecurringSession) -> bool:
    """Checks if a date matches the recurrence pattern of a RecurringSession."""
    # Check if the date is within the period
    if session_date < recurring.start_date:
        return False

    if recurring.end_date and session_date > recurring.end_date:
        return False

    # Check if the weekday is active
    weekday = session_date.weekday()  # 0=Monday, 6=Sunday
    active_weekdays = recurring.get_active_weekdays()

    if weekday not in active_weekdays:
        return False

    # Check based on recurrence_type
    if recurring.recurrence_type == "weekly":
        # Every week - already checked by weekday
        return True

    elif recurring.recurrence_type == "biweekly":
        # Every 2 weeks
        weeks_since_start = (session_date - recurring.start_date).days // 7
        return weeks_since_start % 2 == 0

    elif recurring.recurrence_type == "monthly":
        # Monthly - same calendar day
        return session_date.day == recurring.start_date.day

    return False

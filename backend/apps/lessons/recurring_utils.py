"""
Utility functions for finding recurring sessions that match a session.
"""

from datetime import date

from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession


def find_matching_recurring_session(session: Session) -> RecurringSession | None:
    """
    Finds the RecurringSession that a session belongs to.

    Uses the recurring_session FK when available (set since migration 0011).
    Falls back to pattern matching for legacy sessions without the FK.
    """
    # Fast path: FK is populated
    if session.recurring_session_id is not None:
        return session.recurring_session

    # Fallback: pattern match by contract + start_time for legacy sessions
    recurring_sessions = RecurringSession.objects.filter(
        contract=session.contract,
        start_time=session.start_time,
    )
    for recurring in recurring_sessions:
        if _date_matches_recurring_pattern(session.date, recurring):
            return recurring

    return None


# Alias for backwards compatibility
find_matching_recurring_lesson = find_matching_recurring_session


def get_all_sessions_for_recurring(
    recurring: RecurringSession, original_start_time=None
) -> list[Session]:
    """
    Finds all sessions that belong to a RecurringSession.

    Primary strategy: use the recurring_session FK (set at creation time).
    Fallback: pattern matching by contract + date range + weekday (for legacy
    sessions created before the FK column existed, or during a series edit
    where original_start_time is provided).
    """
    # When called during a series edit we must use the old start_time, so
    # fall through to pattern matching in that case.
    if original_start_time is None:
        fk_sessions = list(Session.objects.filter(recurring_session=recurring))
        if fk_sessions:
            return fk_sessions

    # Fallback: pattern matching (legacy sessions / series-edit path).
    # Does NOT filter by start_time — matches any session on the correct
    # weekday within the date range, regardless of rescheduling.
    start_date = recurring.start_date
    end_date = recurring.end_date
    if not end_date and recurring.contract.end_date:
        end_date = recurring.contract.end_date

    qs = Session.objects.filter(contract=recurring.contract, date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)

    if original_start_time is not None:
        qs = qs.filter(start_time=original_start_time)

    active_weekdays = recurring.get_active_weekdays()
    return [
        s
        for s in qs
        if s.date.weekday() in active_weekdays
        and _date_matches_recurring_pattern(s.date, recurring)
    ]


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
        # Monthly - same calendar day, adjusted for months with fewer days
        from calendar import monthrange

        last_day = monthrange(session_date.year, session_date.month)[1]
        target_day = min(recurring.start_date.day, last_day)
        return session_date.day == target_day

    return False

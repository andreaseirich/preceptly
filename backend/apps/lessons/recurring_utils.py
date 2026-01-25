"""
Utility functions for finding recurring lessons that match a lesson.
"""

from datetime import date

from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson


def find_matching_recurring_lesson(lesson: Lesson) -> RecurringLesson | None:
    """
    Finds the RecurringLesson that a lesson belongs to.

    A lesson belongs to a RecurringLesson if:
    - Same contract
    - Same start time
    - The lesson's date matches the RecurringLesson's recurrence pattern
    """
    # Search for RecurringLessons with the same contract and start time
    recurring_lessons = RecurringLesson.objects.filter(
        contract=lesson.contract,
        start_time=lesson.start_time,
        is_active=True,
    )

    for recurring in recurring_lessons:
        # Check if the lesson's date matches the pattern
        matches = _date_matches_recurring_pattern(lesson.date, recurring)
        if matches:
            return recurring

    return None


def get_all_lessons_for_recurring(
    recurring: RecurringLesson, original_start_time=None
) -> list[Lesson]:
    """
    Finds all lessons that belong to a RecurringLesson.

    This function finds lessons based on the recurrence pattern.
    If original_start_time is provided, it filters by that time
    (useful when the RecurringLesson is being updated).
    """
    # Get all lessons for this contract in the series period
    all_lessons = Lesson.objects.filter(contract=recurring.contract)

    # Determine the period
    start_date = recurring.start_date
    end_date = recurring.end_date
    if not end_date and recurring.contract.end_date:
        end_date = recurring.contract.end_date

    # Filter by date
    if end_date:
        all_lessons = all_lessons.filter(date__gte=start_date, date__lte=end_date)
    else:
        all_lessons = all_lessons.filter(date__gte=start_date)

    # Filter by start_time (if original_start_time is provided, use that, otherwise use current)
    start_time_to_match = (
        original_start_time if original_start_time is not None else recurring.start_time
    )
    all_lessons = all_lessons.filter(start_time=start_time_to_match)

    # Filter by weekday (based on active weekdays)
    recurring.get_active_weekdays()
    matching_lessons = []

    for lesson in all_lessons:
        if _date_matches_recurring_pattern(lesson.date, recurring):
            matching_lessons.append(lesson)

    return matching_lessons


def _date_matches_recurring_pattern(lesson_date: date, recurring: RecurringLesson) -> bool:
    """Checks if a date matches the recurrence pattern of a RecurringLesson."""
    # Check if the date is within the period
    if lesson_date < recurring.start_date:
        return False

    if recurring.end_date and lesson_date > recurring.end_date:
        return False

    # Check if the weekday is active
    weekday = lesson_date.weekday()  # 0=Monday, 6=Sunday
    active_weekdays = recurring.get_active_weekdays()

    if weekday not in active_weekdays:
        return False

    # Check based on recurrence_type
    if recurring.recurrence_type == "weekly":
        # Every week - already checked by weekday
        return True

    elif recurring.recurrence_type == "biweekly":
        # Every 2 weeks
        weeks_since_start = (lesson_date - recurring.start_date).days // 7
        return weeks_since_start % 2 == 0

    elif recurring.recurrence_type == "monthly":
        # Monthly - same calendar day
        return lesson_date.day == recurring.start_date.day

    return False

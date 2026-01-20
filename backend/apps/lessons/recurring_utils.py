"""
Utility functions for finding recurring lessons that match a lesson.
"""

from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from datetime import date


def find_matching_recurring_lesson(lesson: Lesson) -> RecurringLesson | None:
    """
    Findet die RecurringLesson, zu der eine Lesson gehört.
    
    Eine Lesson gehört zu einer RecurringLesson, wenn:
    - Gleicher Contract
    - Gleiche Startzeit
    - Das Datum der Lesson passt zum Wiederholungsmuster der RecurringLesson
    """
    # Suche nach RecurringLessons mit gleichem Contract und Startzeit
    recurring_lessons = RecurringLesson.objects.filter(
        contract=lesson.contract,
        start_time=lesson.start_time,
        is_active=True,
    )
    
    for recurring in recurring_lessons:
        # Prüfe, ob das Datum der Lesson zum Muster passt
        if _date_matches_recurring_pattern(lesson.date, recurring):
            return recurring
    
    return None


def get_all_lessons_for_recurring(recurring: RecurringLesson, original_start_time=None) -> list[Lesson]:
    """
    Findet alle Lessons, die zu einer RecurringLesson gehören.
    
    Diese Funktion findet Lessons basierend auf dem Wiederholungsmuster.
    Wenn original_start_time angegeben ist, wird nach dieser Zeit gefiltert
    (nützlich, wenn die RecurringLesson gerade aktualisiert wird).
    """
    # Hole alle Lessons für diesen Contract im Zeitraum der Serie
    all_lessons = Lesson.objects.filter(contract=recurring.contract)
    
    # Bestimme den Zeitraum
    start_date = recurring.start_date
    end_date = recurring.end_date
    if not end_date and recurring.contract.end_date:
        end_date = recurring.contract.end_date
    
    # Filtere nach Datum
    if end_date:
        all_lessons = all_lessons.filter(date__gte=start_date, date__lte=end_date)
    else:
        all_lessons = all_lessons.filter(date__gte=start_date)
    
    # Filtere nach start_time (wenn original_start_time angegeben, verwende diese, sonst die aktuelle)
    start_time_to_match = original_start_time if original_start_time is not None else recurring.start_time
    all_lessons = all_lessons.filter(start_time=start_time_to_match)
    
    # Filtere nach Wochentag (basierend auf active weekdays)
    active_weekdays = recurring.get_active_weekdays()
    matching_lessons = []
    
    for lesson in all_lessons:
        if _date_matches_recurring_pattern(lesson.date, recurring):
            matching_lessons.append(lesson)
    
    return matching_lessons


def _date_matches_recurring_pattern(lesson_date: date, recurring: RecurringLesson) -> bool:
    """Prüft, ob ein Datum zum Wiederholungsmuster einer RecurringLesson passt."""
    # Prüfe, ob das Datum im Zeitraum liegt
    if lesson_date < recurring.start_date:
        return False
    
    if recurring.end_date and lesson_date > recurring.end_date:
        return False
    
    # Prüfe, ob der Wochentag aktiv ist
    weekday = lesson_date.weekday()  # 0=Monday, 6=Sunday
    active_weekdays = recurring.get_active_weekdays()
    
    if weekday not in active_weekdays:
        return False
    
    # Prüfe basierend auf recurrence_type
    if recurring.recurrence_type == "weekly":
        # Jede Woche - bereits geprüft durch Wochentag
        return True
    
    elif recurring.recurrence_type == "biweekly":
        # Alle 2 Wochen
        weeks_since_start = (lesson_date - recurring.start_date).days // 7
        return weeks_since_start % 2 == 0
    
    elif recurring.recurrence_type == "monthly":
        # Monatlich - gleicher Kalendertag
        return lesson_date.day == recurring.start_date.day
    
    return False

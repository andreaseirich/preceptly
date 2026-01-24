"""
Utility functions for finding recurring blocked times that match a blocked time.
"""

from apps.blocked_times.models import BlockedTime
from apps.blocked_times.recurring_models import RecurringBlockedTime
from datetime import date


def find_matching_recurring_blocked_time(blocked_time: BlockedTime) -> RecurringBlockedTime | None:
    """
    Findet die RecurringBlockedTime, zu der eine BlockedTime gehört.
    
    Eine BlockedTime gehört zu einer RecurringBlockedTime, wenn:
    - Gleicher Titel
    - Gleiche Start- und Endzeit
    - Das Datum der BlockedTime passt zum Wiederholungsmuster der RecurringBlockedTime
    """
    # Suche nach RecurringBlockedTimes mit gleichem Titel und Zeiten
    recurring_blocked_times = RecurringBlockedTime.objects.filter(
        title=blocked_time.title,
        start_time=blocked_time.start_datetime.time(),
        end_time=blocked_time.end_datetime.time(),
        is_active=True,
    )
    
    for recurring in recurring_blocked_times:
        # Prüfe, ob das Datum der BlockedTime zum Muster passt
        matches = _date_matches_recurring_pattern(blocked_time.start_datetime.date(), recurring)
        if matches:
            return recurring
    
    return None


def get_all_blocked_times_for_recurring(recurring: RecurringBlockedTime, original_start_time=None) -> list[BlockedTime]:
    """
    Findet alle BlockedTimes, die zu einer RecurringBlockedTime gehören.
    
    Diese Funktion findet BlockedTimes basierend auf dem Wiederholungsmuster.
    Wenn original_start_time angegeben ist, wird nach dieser Zeit gefiltert
    (nützlich, wenn die RecurringBlockedTime gerade aktualisiert wird).
    """
    # Hole alle BlockedTimes im Zeitraum der Serie
    all_blocked_times = BlockedTime.objects.filter(title=recurring.title)
    
    # Bestimme den Zeitraum
    start_date = recurring.start_date
    end_date = recurring.end_date
    
    # Filtere nach Datum
    if end_date:
        all_blocked_times = all_blocked_times.filter(
            start_datetime__date__gte=start_date, start_datetime__date__lte=end_date
        )
    else:
        all_blocked_times = all_blocked_times.filter(start_datetime__date__gte=start_date)
    
    # Filtere nach start_time (wenn original_start_time angegeben, verwende diese, sonst die aktuelle)
    start_time_to_match = original_start_time if original_start_time is not None else recurring.start_time
    all_blocked_times = all_blocked_times.filter(start_datetime__time=start_time_to_match)
    
    # Filtere nach Wochentag (basierend auf active weekdays)
    active_weekdays = recurring.get_active_weekdays()
    matching_blocked_times = []
    
    for blocked_time in all_blocked_times:
        if _date_matches_recurring_pattern(blocked_time.start_datetime.date(), recurring):
            matching_blocked_times.append(blocked_time)
    
    return matching_blocked_times


def _date_matches_recurring_pattern(blocked_date: date, recurring: RecurringBlockedTime) -> bool:
    """Prüft, ob ein Datum zum Wiederholungsmuster einer RecurringBlockedTime passt."""
    # Prüfe, ob das Datum im Zeitraum liegt
    if blocked_date < recurring.start_date:
        return False
    
    if recurring.end_date and blocked_date > recurring.end_date:
        return False
    
    # Prüfe, ob der Wochentag aktiv ist
    weekday = blocked_date.weekday()  # 0=Monday, 6=Sunday
    active_weekdays = recurring.get_active_weekdays()
    
    if weekday not in active_weekdays:
        return False
    
    # Prüfe basierend auf recurrence_type
    if recurring.recurrence_type == "weekly":
        # Jede Woche - bereits geprüft durch Wochentag
        return True
    
    elif recurring.recurrence_type == "biweekly":
        # Alle 2 Wochen
        weeks_since_start = (blocked_date - recurring.start_date).days // 7
        return weeks_since_start % 2 == 0
    
    elif recurring.recurrence_type == "monthly":
        # Monatlich - gleicher Kalendertag
        return blocked_date.day == recurring.start_date.day
    
    return False

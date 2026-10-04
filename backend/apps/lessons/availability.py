"""Wann ist beim Tutor etwas frei?

Eine Zeit ist belegt, wenn der Tutor dort eine andere Stunde hat (geplant, unterrichtet oder bezahlt, bei
irgendeinem Schüler) oder eine Blockzeit liegt. Dieselbe Regel gilt für die freien Zeiten im Portal, für die
Prüfung bei der Einzelbuchung und für Serien, die Familien im Portal anlegen: Belegte Tage werden dort
ausgelassen, alle anderen gebucht (Anlass: Auftrag von Andreas, 04.10.2026).

Nicht geprüft werden die Arbeitszeiten des Tutors und der Vertragsumfang. Die Einzelbuchung prüft beim
Speichern ebenfalls nur belegte Zeiten.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

LESSON = "lesson"
BLOCKED = "blocked_time"
BUSY_STATUSES = ("planned", "taught", "paid")


class BusyCalendar:
    """Belegte Zeiten eines Tutors für einen Zeitraum.

    Zwei Abfragen für den ganzen Zeitraum statt zwei je Tag - eine Serie über ein Jahr hat leicht 50 Tage.
    Zeiten sind naive Ortszeit."""

    def __init__(self, tutor, first_day, last_day):
        from apps.blocked_times.models import BlockedTime
        from apps.lessons.models import Session

        self._by_day = defaultdict(list)

        sessions = Session.objects.filter(
            contract__user=tutor,
            date__gte=first_day,
            date__lte=last_day,
            status__in=BUSY_STATUSES,
        ).only("date", "start_time", "duration_minutes")
        for session in sessions:
            start = datetime.combine(session.date, session.start_time)
            self._by_day[session.date].append(
                (start, start + timedelta(minutes=session.duration_minutes), LESSON)
            )

        range_start = timezone.make_aware(datetime.combine(first_day, time.min))
        range_end = timezone.make_aware(datetime.combine(last_day, time(23, 59, 59)))
        blocked_times = BlockedTime.objects.filter(
            user=tutor, start_datetime__lt=range_end, end_datetime__gt=range_start
        )
        for blocked in blocked_times:
            blocked_start = timezone.localtime(blocked.start_datetime).replace(tzinfo=None)
            blocked_end = timezone.localtime(blocked.end_datetime).replace(tzinfo=None)
            day = max(blocked_start.date(), first_day)
            last = min(blocked_end.date(), last_day)
            while day <= last:  # mehrtägige Blockzeiten (Urlaub) zählen an jedem Tag
                start = max(blocked_start, datetime.combine(day, time.min))
                end = min(blocked_end, datetime.combine(day, time(23, 59)))
                if start < end:
                    self._by_day[day].append((start, end, BLOCKED))
                day += timedelta(days=1)

    def intervals(self, day):
        """Belegte Zeiten an einem Tag als (Beginn, Ende, Art), Stunden vor Blockzeiten."""
        return list(self._by_day.get(day, []))

    def reason(self, day, start_time, duration_minutes):
        """LESSON oder BLOCKED, wenn die Zeit belegt ist, sonst None. Aneinandergrenzende Zeiten
        (eine Stunde endet genau, wenn die nächste beginnt) überschneiden sich nicht."""
        start = datetime.combine(day, start_time)
        end = start + timedelta(minutes=duration_minutes)
        for busy_start, busy_end, kind in self._by_day.get(day, []):
            if start < busy_end and end > busy_start:
                return kind
        return None


def busy_intervals(tutor, day):
    """Belegte Zeiten eines Tutors an einem Tag als (Beginn, Ende, Art)."""
    return BusyCalendar(tutor, day, day).intervals(day)

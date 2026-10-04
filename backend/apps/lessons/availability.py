"""Wann ist beim Tutor etwas frei?

Eine Zeit ist belegt, wenn der Tutor dort eine andere Stunde hat (geplant, unterrichtet oder bezahlt, bei
irgendeinem Schüler, samt deren Fahrzeit vorher und nachher) oder eine Blockzeit liegt. Dazu kommt der
Mindestabstand aus den Einstellungen des Tutors (UserProfile.min_gap_minutes): Zwischen zwei Terminen und
zwischen Termin und Blockzeit müssen mindestens so viele Minuten liegen. Die Fahrzeit der neuen Stunde zählt
wie bei den vorhandenen zum Termin.

Dieselbe Regel gilt für die freien Zeiten im Portal, für die Prüfung bei Buchung und Verschieben und für Serien,
die Familien im Portal anlegen: Belegte Tage werden dort ausgelassen, alle anderen gebucht.

Nicht geprüft werden die Arbeitszeiten des Tutors und der Vertragsumfang. Die Einzelbuchung prüft beim
Speichern ebenfalls nur belegte Zeiten.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.lessons.spacing import min_gap_minutes

LESSON = "lesson"
BLOCKED = "blocked_time"
BUSY_STATUSES = ("planned", "taught", "paid")


class BusyCalendar:
    """Belegte Zeiten eines Tutors für einen Zeitraum.

    Drei Abfragen für den ganzen Zeitraum (Stunden, Blockzeiten, Mindestabstand) statt zwei je Tag - eine
    Serie über ein Jahr hat leicht 50 Tage. Zeiten sind naive Ortszeit.

    exclude_pk: eine Stunde, die nicht mitzählt (die Stunde, die gerade verschoben wird).
    gap_minutes: Mindestabstand; ohne Angabe aus dem Profil des Tutors."""

    def __init__(self, tutor, first_day, last_day, exclude_pk=None, gap_minutes=None):
        from apps.blocked_times.models import BlockedTime
        from apps.lessons.models import Session

        self.gap = timedelta(minutes=min_gap_minutes(tutor) if gap_minutes is None else gap_minutes)
        self._by_day = defaultdict(list)

        sessions = Session.objects.filter(
            contract__user=tutor,
            date__gte=first_day,
            date__lte=last_day,
            status__in=BUSY_STATUSES,
        )
        if exclude_pk is not None:
            sessions = sessions.exclude(pk=exclude_pk)
        sessions = sessions.only(
            "date",
            "start_time",
            "duration_minutes",
            "travel_time_before_minutes",
            "travel_time_after_minutes",
        )
        for session in sessions:
            start = datetime.combine(session.date, session.start_time)
            self._by_day[session.date].append(
                (
                    start - timedelta(minutes=session.travel_time_before_minutes),
                    start
                    + timedelta(
                        minutes=session.duration_minutes + session.travel_time_after_minutes
                    ),
                    LESSON,
                )
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
        """Belegte Zeiten an einem Tag als (Beginn, Ende, Art), Stunden vor Blockzeiten. Bei Stunden
        samt Fahrzeit, ohne Mindestabstand."""
        return list(self._by_day.get(day, []))

    def reason(self, day, start_time, duration_minutes, travel_before=0, travel_after=0):
        """LESSON oder BLOCKED, wenn die Zeit belegt ist, sonst None.

        Gemeint ist ein neuer Termin mit dieser Dauer und Fahrzeit. Er muss zu jedem belegten Zeitraum
        mindestens den Mindestabstand halten. Aneinandergrenzende Zeiten (eine Stunde endet genau, wenn die
        nächste beginnt) überschneiden sich nicht, solange der Mindestabstand 0 ist."""
        start = datetime.combine(day, start_time)
        block_start = start - timedelta(minutes=travel_before) - self.gap
        block_end = start + timedelta(minutes=duration_minutes + travel_after) + self.gap
        for busy_start, busy_end, kind in self._by_day.get(day, []):
            if block_start < busy_end and block_end > busy_start:
                return kind
        return None


def busy_intervals(tutor, day, exclude_pk=None):
    """Belegte Zeiten eines Tutors an einem Tag als (Beginn, Ende, Art), bei Stunden samt Fahrzeit."""
    return BusyCalendar(tutor, day, day, exclude_pk=exclude_pk).intervals(day)

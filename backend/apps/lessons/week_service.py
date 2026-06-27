"""
Service für Wochenansicht - Gruppierung von Lessons und Blockzeiten nach Tagen und Zeiten.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict

from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService


class _BlockedTimeDayView:
    """Wrapper um eine Blockzeit mit tagesspezifischen Anzeigezeiten für mehrtägige Blockzeiten."""

    __slots__ = (
        "bt",
        "display_start_datetime",
        "display_end_datetime",
        "is_start_day",
        "is_end_day",
    )

    def __init__(self, bt, display_start_datetime, display_end_datetime, is_start_day, is_end_day):
        self.bt = bt
        self.display_start_datetime = display_start_datetime
        self.display_end_datetime = display_end_datetime
        self.is_start_day = is_start_day
        self.is_end_day = is_end_day

    @property
    def pk(self):
        return self.bt.pk

    @property
    def title(self):
        return self.bt.title

    @property
    def start_datetime(self):
        return self.bt.start_datetime

    @property
    def end_datetime(self):
        return self.bt.end_datetime

    @property
    def description(self):
        return self.bt.description


class WeekService:
    """Service für Wochenansicht."""

    @staticmethod
    def get_week_data(year: int, month: int, day: int, user=None) -> Dict:
        """
        Lädt alle Lessons und Blockzeiten für eine Woche (Montag bis Sonntag).

        Args:
            year: Jahr
            month: Monat (1-12)
            day: Tag des Monats (1-31) - wird verwendet, um die Woche zu bestimmen
            user: Optional - filtert Daten nach User (für Multi-Tenancy)

        Returns:
            Dict mit:
            - 'week_start': date (Montag der Woche)
            - 'week_end': date (Sonntag der Woche)
            - 'lessons_by_date': Dict[date, List[Lesson]]
            - 'blocked_times_by_date': Dict[date, List[BlockedTime]]
            - 'conflicts_by_lesson': Dict[Lesson.id, List[conflicts]]
        """
        # Bestimme den Montag der Woche
        target_date = date(year, month, day)
        days_since_monday = target_date.weekday()  # 0=Montag, 6=Sonntag
        week_start = target_date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)  # Sonntag

        # Lade Lessons für die Woche
        lessons_qs = (
            Lesson.objects.filter(date__gte=week_start, date__lte=week_end)
            .select_related("contract")
            .order_by("date", "start_time")
        )
        if user:
            lessons_qs = lessons_qs.filter(contract__user=user)
        lessons = lessons_qs

        # Lade Blockzeiten für die Woche
        start_datetime = timezone.make_aware(datetime.combine(week_start, time.min))
        end_datetime = timezone.make_aware(datetime.combine(week_end, time.max))
        blocked_times_qs = BlockedTime.objects.filter(
            start_datetime__lt=end_datetime, end_datetime__gt=start_datetime
        ).order_by("start_datetime")
        if user:
            blocked_times_qs = blocked_times_qs.filter(user=user)
        blocked_times = blocked_times_qs

        # Gruppiere Lessons nach Datum
        lessons_by_date = defaultdict(list)
        conflicts_by_lesson = {}

        for lesson in lessons:
            lessons_by_date[lesson.date].append(lesson)
            # Prüfe Konflikte
            conflicts = LessonConflictService.check_conflicts(lesson)
            if conflicts:
                conflicts_by_lesson[lesson.id] = conflicts

        # Gruppiere Blockzeiten nach Datum
        blocked_times_by_date = defaultdict(list)
        # Sichtbarer Tagesbereich im Kalender (8–22 Uhr)
        _DAY_START = time(8, 0)
        _DAY_END = time(22, 59, 59)

        for blocked_time in blocked_times:
            bt_start_date = blocked_time.start_datetime.date()
            bt_end_date = blocked_time.end_datetime.date()
            is_multiday = bt_start_date != bt_end_date

            current_date = bt_start_date
            while current_date <= bt_end_date and current_date <= week_end:
                if current_date >= week_start:
                    is_start = current_date == bt_start_date
                    is_end = current_date == bt_end_date

                    if is_multiday and not is_start:
                        # Mittlere und End-Tage beginnen am Anfang des sichtbaren Bereichs
                        disp_start = timezone.make_aware(datetime.combine(current_date, _DAY_START))
                    else:
                        disp_start = blocked_time.start_datetime

                    if is_multiday and not is_end:
                        # Start- und Zwischen-Tage enden am Ende des sichtbaren Bereichs
                        disp_end = timezone.make_aware(datetime.combine(current_date, _DAY_END))
                    else:
                        disp_end = blocked_time.end_datetime

                    blocked_times_by_date[current_date].append(
                        _BlockedTimeDayView(
                            bt=blocked_time,
                            display_start_datetime=disp_start,
                            display_end_datetime=disp_end,
                            is_start_day=is_start,
                            is_end_day=is_end,
                        )
                    )
                current_date += timedelta(days=1)

        return {
            "week_start": week_start,
            "week_end": week_end,
            "lessons_by_date": dict(lessons_by_date),
            "blocked_times_by_date": dict(blocked_times_by_date),
            "conflicts_by_lesson": conflicts_by_lesson,
        }

"""
Service für Kalenderansicht - Gruppierung von Lessons und Blockzeiten nach Tagen.
"""

from collections import defaultdict
from datetime import date, datetime
from typing import Dict

from apps.blocked_times.models import BlockedTime
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService
from django.utils import timezone


class CalendarService:
    """Service für Kalenderansicht."""

    @staticmethod
    def get_calendar_data(year: int, month: int, user=None) -> Dict:
        """
        Lädt alle Lessons und Blockzeiten für einen Monat und gruppiert sie nach Tagen.

        Args:
            year: Jahr
            month: Monat (1-12)
            user: Optional - filtert Daten nach User (für Multi-Tenancy)

        Returns:
            Dict mit:
            - 'lessons_by_date': Dict[date, List[Lesson]]
            - 'blocked_times_by_date': Dict[date, List[BlockedTime]]
            - 'conflicts_by_lesson': Dict[Lesson.id, List[conflicts]]
        """
        # Datumsbereich für den Monat
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        # Lade Lessons - alle Lessons im Monatsbereich (Vergangenheit und Zukunft)
        lessons_qs = (
            Lesson.objects.filter(date__gte=start_date, date__lt=end_date)
            .select_related("contract", "contract__student")
            .order_by("date", "start_time")
        )
        if user:
            lessons_qs = lessons_qs.filter(contract__student__user=user)
        lessons = lessons_qs

        # Lade Blockzeiten im Monatsbereich
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.min.time()))
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
        for blocked_time in blocked_times:
            # Blockzeiten können mehrere Tage umfassen
            from datetime import timedelta

            current_date = blocked_time.start_datetime.date()
            end_date_bt = blocked_time.end_datetime.date()

            # Füge für jeden betroffenen Tag hinzu
            while current_date <= end_date_bt and current_date < end_date:
                if current_date >= start_date:
                    blocked_times_by_date[current_date].append(blocked_time)
                current_date += timedelta(days=1)

        return {
            "lessons_by_date": dict(lessons_by_date),
            "blocked_times_by_date": dict(blocked_times_by_date),
            "conflicts_by_lesson": conflicts_by_lesson,
        }

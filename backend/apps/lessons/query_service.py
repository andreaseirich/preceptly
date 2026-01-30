"""
Service for session queries and filtering.
"""

from datetime import date, timedelta

from apps.lessons.models import Session
from django.contrib.auth.models import User
from django.utils import timezone


class SessionQueryService:
    """Service for session queries and filtering."""

    @staticmethod
    def get_sessions_for_month(year: int, month: int, user: User = None) -> list[Session]:
        """
        Returns all sessions for a specific month.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            List of Session objects
        """
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        qs = (
            Session.objects.filter(date__gte=start_date, date__lt=end_date)
            .select_related("contract", "contract__student")
            .order_by("date", "start_time")
        )
        if user:
            qs = qs.filter(contract__student__user=user)
        return qs

    @staticmethod
    def get_today_sessions(user: User = None) -> list[Session]:
        """Returns all sessions for today."""
        today = timezone.now().date()
        qs = (
            Session.objects.filter(date=today)
            .select_related("contract", "contract__student")
            .order_by("start_time")
        )
        if user:
            qs = qs.filter(contract__student__user=user)
        return qs

    @staticmethod
    def get_upcoming_sessions(days: int = 7, user: User = None) -> list[Session]:
        """
        Returns upcoming sessions (excluding today's sessions).

        Today's sessions are excluded as they are already shown in
        the separate "Today" section.

        Args:
            days: Number of days into the future (starting from tomorrow)

        Returns:
            List of Session objects (from tomorrow up to today + days)
        """
        today = timezone.now().date()
        end_date = today + timedelta(days=days)

        # Only sessions from tomorrow (date > today), not today
        qs = (
            Session.objects.filter(date__gt=today, date__lte=end_date)
            .select_related("contract", "contract__student")
            .order_by("date", "start_time")
        )
        if user:
            qs = qs.filter(contract__student__user=user)
        return qs[:10]


# Alias for backwards compatibility
LessonQueryService = SessionQueryService

# Add method aliases for backwards compatibility
LessonQueryService.get_today_lessons = SessionQueryService.get_today_sessions
LessonQueryService.get_upcoming_lessons = SessionQueryService.get_upcoming_sessions
LessonQueryService.get_lessons_for_month = SessionQueryService.get_sessions_for_month

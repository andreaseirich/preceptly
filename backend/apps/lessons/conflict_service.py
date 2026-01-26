"""
Service for conflict detection and recalculation.
"""

from datetime import datetime, timedelta

from apps.blocked_times.models import BlockedTime
from apps.lessons.models import Session
from apps.lessons.quota_service import ContractQuotaService
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _


def recalculate_conflicts_for_affected_sessions(session: Session):
    """
    Recalculates conflicts for a session and all potentially affected sessions.

    This should be called after a session is created, updated, or deleted
    to ensure all conflict flags are up to date.

    Args:
        session: The session that was changed
    """
    # Recalculate conflicts for the session itself (if it still exists)
    if session.pk:
        # This will be done when the session is accessed, but we can force it here
        pass

    # Find all sessions on the same date that might be affected
    affected_sessions = Session.objects.filter(date=session.date).exclude(
        pk=session.pk if session.pk else None
    )

    # Recalculate conflicts for affected sessions
    # (The conflicts will be recalculated on-demand when accessed)
    # But we can trigger a check here to ensure consistency
    for affected_session in affected_sessions:
        # Force conflict check (this will be cached in the property)
        affected_session.get_conflicts()


# Alias for backwards compatibility
recalculate_conflicts_for_affected_lessons = recalculate_conflicts_for_affected_sessions


def recalculate_conflicts_for_blocked_time(blocked_time: BlockedTime):
    """
    Recalculates conflicts for all sessions that might be affected by a blocked time change.

    Args:
        blocked_time: The blocked time that was changed or deleted
    """
    # Find all sessions that might overlap with this blocked time
    start_datetime = blocked_time.start_datetime

    # Find sessions on the same date
    affected_sessions = Session.objects.filter(date=start_datetime.date())

    # Check each session for conflicts with this blocked time
    for session in affected_sessions:
        # Force conflict check
        session.get_conflicts()


class SessionConflictService:
    """Service for conflict detection in sessions."""

    @staticmethod
    def intervals_overlap(
        start1: datetime, end1: datetime, start2: datetime, end2: datetime
    ) -> bool:
        """
        Checks if two time intervals overlap.

        Two intervals overlap if:
        - end1 > start2 AND start1 < end2

        Args:
            start1: Start of first interval
            end1: End of first interval
            start2: Start of second interval
            end2: End of second interval

        Returns:
            True if overlap, otherwise False
        """
        return end1 > start2 and start1 < end2

    @staticmethod
    def calculate_time_block(session: Session) -> tuple[datetime, datetime]:
        """
        Calculates the total time block of a session including travel times.

        Args:
            session: Session object

        Returns:
            Tuple (start_datetime, end_datetime) with timezone-aware datetime
        """
        # Combine date and start time
        session_datetime = timezone.make_aware(datetime.combine(session.date, session.start_time))

        # Start = start time - travel time before
        start_datetime = session_datetime - timedelta(minutes=session.travel_time_before_minutes)

        # End = start time + duration + travel time after
        end_datetime = session_datetime + timedelta(
            minutes=session.duration_minutes + session.travel_time_after_minutes
        )

        return start_datetime, end_datetime

    @staticmethod
    def check_conflicts(session: Session, exclude_self: bool = True) -> list[dict]:
        """
        Checks if a session has conflicts with other sessions or blocked times.

        Args:
            session: Session object
            exclude_self: If True, the session itself is excluded from the check

        Returns:
            List of conflict dicts with 'type', 'object', 'message'
        """
        conflicts = []
        start_datetime, end_datetime = SessionConflictService.calculate_time_block(session)

        # Check conflicts with other sessions
        query = Q(date=session.date, start_time__isnull=False)

        if exclude_self and session.pk:
            query &= ~Q(pk=session.pk)

        other_sessions = Session.objects.filter(query).select_related(
            "contract", "contract__student"
        )

        for other_session in other_sessions:
            other_start, other_end = SessionConflictService.calculate_time_block(other_session)

            # Check overlap with explicit helper function
            if SessionConflictService.intervals_overlap(
                start1=start_datetime, end1=end_datetime, start2=other_start, end2=other_end
            ):
                conflicts.append(
                    {
                        "type": "session",
                        "object": other_session,
                        "message": _("Overlap with session for {student} ({time})").format(
                            student=other_session.contract.student,
                            time=other_session.start_time.strftime("%H:%M"),
                        ),
                        "start": other_start,
                        "end": other_end,
                    }
                )

        # Check conflicts with blocked times
        # Use a broader query, but then explicitly check for overlap
        # Filter by date to improve performance (for multi-day blocked times)
        # Find blocked times that could overlap: start before session ends, end after session starts
        blocked_times = BlockedTime.objects.filter(
            start_datetime__lt=end_datetime, end_datetime__gt=start_datetime
        )

        for blocked_time in blocked_times:
            # Explicit overlap check with helper function
            if SessionConflictService.intervals_overlap(
                start1=start_datetime,
                end1=end_datetime,
                start2=blocked_time.start_datetime,
                end2=blocked_time.end_datetime,
            ):
                conflicts.append(
                    {
                        "type": "blocked_time",
                        "object": blocked_time,
                        "message": _("Overlap with blocked time: {title}").format(
                            title=blocked_time.title
                        ),
                        "start": blocked_time.start_datetime,
                        "end": blocked_time.end_datetime,
                    }
                )

        # Check quota conflict
        quota_conflict = ContractQuotaService.check_quota_conflict(session, exclude_self)
        if quota_conflict:
            conflicts.append(
                {
                    "type": "quota",
                    "object": session.contract,
                    "message": quota_conflict["message"],
                    "planned_total": quota_conflict["planned_total"],
                    "actual_total": quota_conflict["actual_total"],
                    "month": quota_conflict["month"],
                    "year": quota_conflict["year"],
                }
            )

        return conflicts

    @staticmethod
    def has_conflicts(session: Session, exclude_self: bool = True) -> bool:
        """
        Checks if a session has conflicts (simplified version).

        Args:
            session: Session object
            exclude_self: If True, the session itself is excluded

        Returns:
            True if conflicts exist, otherwise False
        """
        return len(SessionConflictService.check_conflicts(session, exclude_self)) > 0


# Alias for backwards compatibility
LessonConflictService = SessionConflictService

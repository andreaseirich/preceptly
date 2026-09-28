"""
Service for conflict detection and recalculation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.apps import apps
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.blocked_times.models import BlockedTime
from apps.lessons.quota_service import ContractQuotaService

if TYPE_CHECKING:
    from apps.lessons.models import Session


def recalculate_conflicts_for_affected_sessions(session: Session):
    """
    Recalculates conflicts for a session and all potentially affected sessions.

    This should be called after a session is created, updated, or deleted
    to ensure all conflict flags are up to date. Only sessions of the same user
    are considered (multi-tenancy).

    Args:
        session: The session that was changed
    """
    owner_user = session.contract.user

    # Find all sessions on the same date of the same user that might be affected
    Session = apps.get_model("lessons", "Session")
    affected_sessions = Session.objects.filter(
        date=session.date, contract__user=owner_user
    ).exclude(pk=session.pk if session.pk else None)

    for affected_session in affected_sessions:
        # Force conflict check (clears cached conflicts)
        affected_session.get_conflicts()


# Alias for backwards compatibility
recalculate_conflicts_for_affected_lessons = recalculate_conflicts_for_affected_sessions


def recalculate_conflicts_for_blocked_time(blocked_time: BlockedTime):
    """
    Recalculates conflicts for all sessions that might be affected by a blocked time change.

    Only sessions of the same user as the blocked time are considered (multi-tenancy).

    Args:
        blocked_time: The blocked time that was changed or deleted
    """
    # Find sessions on ALL dates covered by the blocked time (supports multi-day)
    Session = apps.get_model("lessons", "Session")
    affected_sessions = Session.objects.filter(
        date__gte=blocked_time.start_datetime.date(),
        date__lte=blocked_time.end_datetime.date(),
        contract__user=blocked_time.user,
    )

    for session in affected_sessions:
        # Force conflict check (clears cached conflicts)
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
    def _lesson_conflicts(session, start, end, candidates, exclude_self: bool) -> list[dict]:
        """Überschneidungen mit anderen Stunden - reine Rechnung über fertige Kandidaten
        (Stunden desselben Tutors am selben Tag)."""
        conflicts = []
        for other_session in candidates:
            if exclude_self and session.pk and other_session.pk == session.pk:
                continue
            other_start, other_end = SessionConflictService.calculate_time_block(other_session)
            if SessionConflictService.intervals_overlap(
                start1=start, end1=end, start2=other_start, end2=other_end
            ):
                conflicts.append(
                    {
                        "type": "lesson",
                        "object": other_session,
                        "message": _("Overlap with lesson for {student} ({time})").format(
                            student=other_session.contract,
                            time=other_session.start_time.strftime("%H:%M"),
                        ),
                        "start": other_start,
                        "end": other_end,
                    }
                )
        return conflicts

    @staticmethod
    def _blocked_time_conflicts(start, end, blocked_times) -> list[dict]:
        """Überschneidungen mit Sperrzeiten - reine Rechnung."""
        conflicts = []
        for blocked_time in blocked_times:
            if SessionConflictService.intervals_overlap(
                start1=start,
                end1=end,
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
        return conflicts

    @staticmethod
    def _quota_entry(session, quota_conflict) -> dict | None:
        if not quota_conflict:
            return None
        return {
            "type": "quota",
            "object": session.contract,
            "message": quota_conflict["message"],
            "planned_total": quota_conflict["planned_total"],
            "actual_total": quota_conflict["actual_total"],
            "month": quota_conflict["month"],
            "year": quota_conflict["year"],
        }

    @staticmethod
    def check_conflicts(session: Session, exclude_self: bool = True) -> list[dict]:
        """
        Checks if a session has conflicts with other sessions or blocked times.

        Für viele Stunden auf einmal: check_conflicts_bulk (gleiche Regeln, wenige
        Abfragen statt vier pro Stunde).

        Args:
            session: Session object
            exclude_self: If True, the session itself is excluded from the check

        Returns:
            List of conflict dicts with 'type', 'object', 'message'
        """
        start_datetime, end_datetime = SessionConflictService.calculate_time_block(session)
        # Only sessions and blocked times of the same user (multi-tenancy)
        owner_user = session.contract.user

        Session = apps.get_model("lessons", "Session")
        candidates = Session.objects.filter(
            date=session.date, start_time__isnull=False, contract__user=owner_user
        ).select_related("contract")
        conflicts = SessionConflictService._lesson_conflicts(
            session, start_datetime, end_datetime, candidates, exclude_self
        )

        blocked_times = BlockedTime.objects.filter(
            user=owner_user,
            start_datetime__lt=end_datetime,
            end_datetime__gt=start_datetime,
        )
        conflicts += SessionConflictService._blocked_time_conflicts(
            start_datetime, end_datetime, blocked_times
        )

        quota = SessionConflictService._quota_entry(
            session, ContractQuotaService.check_quota_conflict(session, exclude_self)
        )
        if quota:
            conflicts.append(quota)
        return conflicts

    @staticmethod
    def check_conflicts_bulk(sessions, exclude_self: bool = True) -> dict[int, list[dict]]:
        """check_conflicts für viele Stunden auf einmal: {session.pk: [Konflikte]}.

        Dieselben Rechenfunktionen, aber die Daten kommen in fünf Abfragen statt
        vier pro Stunde - für Wochenansicht, Dashboard und Monatsansicht, die sonst
        mit jeder Stunde langsamer wurden (Prüfbericht 27.09.2026, L2).
        """
        sessions = [s for s in sessions if s.pk]
        if not sessions:
            return {}
        Session = apps.get_model("lessons", "Session")
        Contract = apps.get_model("contracts", "Contract")

        contracts = Contract.objects.in_bulk({s.contract_id for s in sessions})
        for s in sessions:
            s.contract = contracts[s.contract_id]
        owners = {c.user_id for c in contracts.values()}
        blocks = {s.pk: SessionConflictService.calculate_time_block(s) for s in sessions}

        candidates = defaultdict(list)
        for other in Session.objects.filter(
            date__in={s.date for s in sessions},
            start_time__isnull=False,
            contract__user_id__in=owners,
        ).select_related("contract"):
            candidates[(other.contract.user_id, other.date)].append(other)

        blocked = defaultdict(list)
        for blocked_time in BlockedTime.objects.filter(
            user_id__in=owners,
            start_datetime__lt=max(end for _start, end in blocks.values()),
            end_datetime__gt=min(start for start, _end in blocks.values()),
        ):
            blocked[blocked_time.user_id].append(blocked_time)

        quota_data = ContractQuotaService.preload(sessions)

        result = {}
        for s in sessions:
            start, end = blocks[s.pk]
            owner = s.contract.user_id
            conflicts = SessionConflictService._lesson_conflicts(
                s, start, end, candidates[(owner, s.date)], exclude_self
            )
            conflicts += SessionConflictService._blocked_time_conflicts(start, end, blocked[owner])
            quota = SessionConflictService._quota_entry(
                s, ContractQuotaService.quota_conflict_from_preloaded(s, quota_data, exclude_self)
            )
            if quota:
                conflicts.append(quota)
            result[s.pk] = conflicts
        return result

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

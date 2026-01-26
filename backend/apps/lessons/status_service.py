"""
Service for automatically updating session statuses based on date/time.
"""

from datetime import datetime, timedelta

from apps.lessons.models import Session
from django.db import transaction
from django.utils import timezone


class SessionStatusUpdater:
    """
    Service class for automatic status updates of sessions.

    Automatically sets sessions with status 'planned' to 'taught' once
    their end time is in the past.
    """

    @staticmethod
    def update_status_for_session(session: Session) -> bool:
        """
        Updates the status of a single session based on date/time.

        Rules:
        - If end_datetime < now and status PLANNED → set to TAUGHT
        - If start_datetime >= now and status empty/None → set to PLANNED
        - PAID or CANCELLED are NOT overwritten

        Args:
            session: The session instance

        Returns:
            True if status was changed, False otherwise
        """
        now = timezone.now()

        # Calculate start_datetime and end_datetime
        start_datetime = timezone.make_aware(datetime.combine(session.date, session.start_time))
        end_datetime = start_datetime + timedelta(minutes=session.duration_minutes)

        # Do not overwrite PAID or CANCELLED status
        if session.status in ["paid", "cancelled"]:
            return False

        status_changed = False

        # Past session (end_datetime < now) with PLANNED or empty status → TAUGHT
        if end_datetime < now and (
            session.status == "planned" or not session.status or session.status == ""
        ):
            session.status = "taught"
            status_changed = True

        # Future session (start_datetime >= now) without status → PLANNED
        elif start_datetime >= now and (not session.status or session.status == ""):
            session.status = "planned"
            status_changed = True

        # Save only if session is already saved (has PK)
        if status_changed and session.pk:
            session.save(update_fields=["status", "updated_at"])

        return status_changed

    @staticmethod
    def update_past_sessions_to_taught(now=None) -> int:
        """
        Sets all sessions with status 'planned' to 'taught' whose end time
        is in the past.

        Rules:
        - Only sessions with status 'planned' are updated
        - Sessions with status 'paid' or 'cancelled' are NOT changed
        - End time = start_datetime + duration_minutes (without travel times)

        Args:
            now: Optional datetime object (default: timezone.now())

        Returns:
            Number of updated sessions
        """
        if now is None:
            now = timezone.now()

        # Wrap the entire operation in a transaction, as select_for_update() requires a transaction
        with transaction.atomic():
            # Load all sessions with status 'planned'
            # Use select_for_update for thread-safety (optional, but clean)
            sessions = Session.objects.filter(status="planned").select_for_update(skip_locked=True)

            updated_sessions = []

            for session in sessions:
                # Calculate end_datetime (only session duration, without travel times)
                start_datetime = timezone.make_aware(
                    datetime.combine(session.date, session.start_time)
                )
                end_datetime = start_datetime + timedelta(minutes=session.duration_minutes)

                # If end time is in the past, mark for update
                if end_datetime < now:
                    session.status = "taught"
                    updated_sessions.append(session)

            # Bulk update for performance
            if updated_sessions:
                Session.objects.bulk_update(
                    updated_sessions, fields=["status", "updated_at"], batch_size=100
                )

        return len(updated_sessions)


# Aliases for backwards compatibility
LessonStatusUpdater = SessionStatusUpdater
LessonStatusService = SessionStatusUpdater

# Add method aliases for backwards compatibility
LessonStatusUpdater.update_past_lessons_to_taught = (
    SessionStatusUpdater.update_past_sessions_to_taught
)
LessonStatusUpdater.update_status_for_lesson = SessionStatusUpdater.update_status_for_session

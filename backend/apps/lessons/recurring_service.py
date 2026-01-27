"""
Service for recurring sessions (series appointments).
"""

from datetime import date, timedelta
from typing import List

from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession


class RecurringSessionService:
    """Service for generating sessions from RecurringSession templates."""

    @staticmethod
    def generate_sessions(
        recurring_session: RecurringSession, check_conflicts: bool = True, dry_run: bool = False
    ) -> dict:
        """
        Generates sessions for a RecurringSession over the period [start_date, end_date].

        Args:
            recurring_session: The RecurringSession template
            check_conflicts: Whether to check for conflicts
            dry_run: If True, no sessions are saved, only preview

        Returns:
            Dict with:
            - 'created': Number of created sessions
            - 'skipped': Number of skipped (already existing)
            - 'conflicts': List of conflicts (if check_conflicts=True)
            - 'preview': List of Session instances (if dry_run=True)
        """
        if not recurring_session.is_active:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": [], "sessions": []}

        # Determine end date
        end_date = recurring_session.end_date
        if not end_date:
            # If no end date, use contract end date or 1 year
            if recurring_session.contract.end_date:
                end_date = recurring_session.contract.end_date
            else:
                end_date = date(
                    recurring_session.start_date.year + 1,
                    recurring_session.start_date.month,
                    recurring_session.start_date.day,
                )

        # Generate sessions based on recurrence_type
        recurrence_type = recurring_session.recurrence_type

        if recurrence_type == "weekly":
            return RecurringSessionService._generate_weekly_sessions(
                recurring_session, end_date, check_conflicts, dry_run
            )
        elif recurrence_type == "biweekly":
            return RecurringSessionService._generate_biweekly_sessions(
                recurring_session, end_date, check_conflicts, dry_run
            )
        elif recurrence_type == "monthly":
            return RecurringSessionService._generate_monthly_sessions(
                recurring_session, end_date, check_conflicts, dry_run
            )
        else:
            # Fallback to weekly for unknown types
            return RecurringSessionService._generate_weekly_sessions(
                recurring_session, end_date, check_conflicts, dry_run
            )

    @staticmethod
    def _generate_weekly_sessions(
        recurring_session: RecurringSession, end_date: date, check_conflicts: bool, dry_run: bool
    ) -> dict:
        """Generates weekly sessions."""
        active_weekdays = recurring_session.get_active_weekdays()

        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": [], "sessions": []}

        current_date = recurring_session.start_date
        created = 0
        skipped = 0
        conflicts = []
        preview = []
        sessions = []  # Collect created sessions for email notifications
        dates_checked = []

        while current_date <= end_date:
            weekday = current_date.weekday()  # 0=Monday, 6=Sunday

            if weekday in active_weekdays:
                dates_checked.append(str(current_date))
                result = RecurringSessionService._create_session_if_not_exists(
                    recurring_session, current_date, check_conflicts, dry_run
                )
                if result["created"]:
                    created += 1
                    if result.get("session"):
                        if dry_run:
                            preview.append(result["session"])
                        else:
                            # Collect created sessions for email notifications
                            sessions.append(result["session"])
                        if result.get("conflicts"):
                            conflicts.extend(result["conflicts"])
                elif result["skipped"]:
                    skipped += 1

            current_date += timedelta(days=1)

        return {
            "created": created,
            "skipped": skipped,
            "conflicts": conflicts,
            "preview": preview if dry_run else [],
            "sessions": sessions if not dry_run else [],
        }

    @staticmethod
    def _generate_biweekly_sessions(
        recurring_session: RecurringSession, end_date: date, check_conflicts: bool, dry_run: bool
    ) -> dict:
        """Generates bi-weekly sessions (every 2 weeks)."""
        active_weekdays = recurring_session.get_active_weekdays()
        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": [], "sessions": []}

        current_date = recurring_session.start_date
        created = 0
        skipped = 0
        conflicts = []
        preview = []
        sessions = []  # Collect created sessions for email notifications

        # Count weeks since start
        week_count = 0

        while current_date <= end_date:
            weekday = current_date.weekday()

            if weekday in active_weekdays:
                # Only every 2nd week (even week number)
                if week_count % 2 == 0:
                    result = RecurringSessionService._create_session_if_not_exists(
                        recurring_session, current_date, check_conflicts, dry_run
                    )
                    if result["created"]:
                        created += 1
                        if result.get("session"):
                            if dry_run:
                                preview.append(result["session"])
                            else:
                                # Collect created sessions for email notifications
                                sessions.append(result["session"])
                            if result.get("conflicts"):
                                conflicts.extend(result["conflicts"])
                    elif result["skipped"]:
                        skipped += 1

            # When we reach a Monday, increment week counter
            if weekday == 0:  # Monday
                week_count += 1

            current_date += timedelta(days=1)

        return {
            "created": created,
            "skipped": skipped,
            "conflicts": conflicts,
            "preview": preview if dry_run else [],
            "sessions": sessions if not dry_run else [],
        }

    @staticmethod
    def _generate_monthly_sessions(
        recurring_session: RecurringSession, end_date: date, check_conflicts: bool, dry_run: bool
    ) -> dict:
        """Generates monthly sessions (same calendar day every month)."""
        active_weekdays = recurring_session.get_active_weekdays()
        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": [], "sessions": []}

        created = 0
        skipped = 0
        conflicts = []
        preview = []
        sessions = []  # Collect created sessions for email notifications

        # Start with the start date
        current_date = recurring_session.start_date
        start_day = current_date.day  # Day of month (e.g., 15th)

        from calendar import monthrange

        while current_date <= end_date:
            # Check if current date is the correct day of month
            # AND if it is an active weekday
            target_day = start_day
            # If the day doesn't exist in the current month (e.g., Feb 31),
            # use the last day of the month
            last_day_of_month = monthrange(current_date.year, current_date.month)[1]
            if start_day > last_day_of_month:
                target_day = last_day_of_month

            if current_date.day == target_day and current_date.weekday() in active_weekdays:
                result = RecurringSessionService._create_session_if_not_exists(
                    recurring_session, current_date, check_conflicts, dry_run
                )
                if result["created"]:
                    created += 1
                    if result.get("session"):
                        if dry_run:
                            preview.append(result["session"])
                        else:
                            # Collect created sessions for email notifications
                            sessions.append(result["session"])
                        if result.get("conflicts"):
                            conflicts.extend(result["conflicts"])
                elif result["skipped"]:
                    skipped += 1

            # Jump to next month
            # Calculate the next month
            if current_date.month == 12:
                next_year = current_date.year + 1
                next_month = 1
            else:
                next_year = current_date.year
                next_month = current_date.month + 1

            # Try the same day in the next month
            last_day_next_month = monthrange(next_year, next_month)[1]
            target_day_next = min(start_day, last_day_next_month)

            try:
                current_date = date(next_year, next_month, target_day_next)
            except ValueError:
                # Fallback: last day of month
                current_date = date(next_year, next_month, last_day_next_month)

        return {
            "created": created,
            "skipped": skipped,
            "conflicts": conflicts,
            "preview": preview if dry_run else [],
            "sessions": sessions if not dry_run else [],
        }

    @staticmethod
    def _create_session_if_not_exists(
        recurring_session: RecurringSession,
        session_date: date,
        check_conflicts: bool,
        dry_run: bool,
    ) -> dict:
        """Helper method: Creates a session if it doesn't exist yet."""
        # Check if a session already exists for this day
        existing = Session.objects.filter(
            contract=recurring_session.contract,
            date=session_date,
            start_time=recurring_session.start_time,
        ).first()

        if existing:
            return {"created": False, "skipped": True}

        # Create new session (without status - will be set automatically)
        session = Session(
            contract=recurring_session.contract,
            date=session_date,
            start_time=recurring_session.start_time,
            duration_minutes=recurring_session.duration_minutes,
            travel_time_before_minutes=recurring_session.travel_time_before_minutes,
            travel_time_after_minutes=recurring_session.travel_time_after_minutes,
            status="",  # Empty - will be set automatically
            notes=recurring_session.notes,
        )

        # Automatic status setting (before saving)
        from apps.lessons.status_service import SessionStatusUpdater

        SessionStatusUpdater.update_status_for_session(session)

        result = {"created": True, "skipped": False, "session": session, "conflicts": []}

        if not dry_run:
            session.save()
            # Set status again after saving (if necessary)
            SessionStatusUpdater.update_status_for_session(session)
            session.refresh_from_db()  # Refresh to get updated status

            # Check conflicts
            if check_conflicts:
                from apps.lessons.services import SessionConflictService

                session_conflicts = SessionConflictService.check_conflicts(session)
                if session_conflicts:
                    result["conflicts"] = [
                        {"session": session, "date": session_date, "conflicts": session_conflicts}
                    ]

        return result

    @staticmethod
    def preview_sessions(recurring_session: RecurringSession) -> List[Session]:
        """
        Returns a preview of sessions to be generated (without saving).

        Args:
            recurring_session: The RecurringSession template

        Returns:
            List of Session instances (not saved)
        """
        result = RecurringSessionService.generate_sessions(
            recurring_session, check_conflicts=False, dry_run=True
        )
        return result.get("preview", [])


# Aliases for backwards compatibility
RecurringLessonService = RecurringSessionService
# Alias for method name
RecurringSessionService.preview_lessons = RecurringSessionService.preview_sessions

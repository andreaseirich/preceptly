"""
Service für wiederholende Unterrichtsstunden (Recurring Lessons).
"""

from datetime import date, timedelta
from typing import List

from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.services import LessonConflictService
from apps.lessons.status_service import LessonStatusService


class RecurringLessonService:
    """Service für die Generierung von Lessons aus RecurringLesson-Vorlagen."""

    @staticmethod
    def generate_lessons(
        recurring_lesson: RecurringLesson, check_conflicts: bool = True, dry_run: bool = False
    ) -> dict:
        """
        Generiert Lessons für eine RecurringLesson über den Zeitraum [start_date, end_date].

        Args:
            recurring_lesson: Die RecurringLesson-Vorlage
            check_conflicts: Ob Konflikte geprüft werden sollen
            dry_run: Wenn True, werden keine Lessons gespeichert, nur Vorschau

        Returns:
            Dict mit:
            - 'created': Anzahl erstellter Lessons
            - 'skipped': Anzahl übersprungener (bereits vorhandene)
            - 'conflicts': Liste von Konflikten (wenn check_conflicts=True)
            - 'preview': Liste von Lesson-Instanzen (wenn dry_run=True)
        """
        if not recurring_lesson.is_active:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": []}

        # Determine end date
        end_date = recurring_lesson.end_date
        if not end_date:
            # If no end date, use contract end date or 1 year
            if recurring_lesson.contract.end_date:
                end_date = recurring_lesson.contract.end_date
            else:
                end_date = date(
                    recurring_lesson.start_date.year + 1,
                    recurring_lesson.start_date.month,
                    recurring_lesson.start_date.day,
                )

        # Generate lessons based on recurrence_type
        recurrence_type = recurring_lesson.recurrence_type

        if recurrence_type == "weekly":
            return RecurringLessonService._generate_weekly_lessons(
                recurring_lesson, end_date, check_conflicts, dry_run
            )
        elif recurrence_type == "biweekly":
            return RecurringLessonService._generate_biweekly_lessons(
                recurring_lesson, end_date, check_conflicts, dry_run
            )
        elif recurrence_type == "monthly":
            return RecurringLessonService._generate_monthly_lessons(
                recurring_lesson, end_date, check_conflicts, dry_run
            )
        else:
            # Fallback to weekly for unknown types
            return RecurringLessonService._generate_weekly_lessons(
                recurring_lesson, end_date, check_conflicts, dry_run
            )

    @staticmethod
    def _generate_weekly_lessons(
        recurring_lesson: RecurringLesson, end_date: date, check_conflicts: bool, dry_run: bool
    ) -> dict:
        """Generiert wöchentliche Lessons."""
        active_weekdays = recurring_lesson.get_active_weekdays()

        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": []}

        current_date = recurring_lesson.start_date
        created = 0
        skipped = 0
        conflicts = []
        preview = []
        dates_checked = []

        while current_date <= end_date:
            weekday = current_date.weekday()  # 0=Montag, 6=Sonntag

            if weekday in active_weekdays:
                dates_checked.append(str(current_date))
                result = RecurringLessonService._create_lesson_if_not_exists(
                    recurring_lesson, current_date, check_conflicts, dry_run
                )
                if result["created"]:
                    created += 1
                    if result.get("lesson"):
                        if dry_run:
                            preview.append(result["lesson"])
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
        }

    @staticmethod
    def _generate_biweekly_lessons(
        recurring_lesson: RecurringLesson, end_date: date, check_conflicts: bool, dry_run: bool
    ) -> dict:
        """Generiert zweiwöchentliche Lessons (alle 2 Wochen)."""
        active_weekdays = recurring_lesson.get_active_weekdays()
        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": []}

        current_date = recurring_lesson.start_date
        created = 0
        skipped = 0
        conflicts = []
        preview = []

        # Count weeks since start
        week_count = 0

        while current_date <= end_date:
            weekday = current_date.weekday()

            if weekday in active_weekdays:
                # Only every 2nd week (even week number)
                if week_count % 2 == 0:
                    result = RecurringLessonService._create_lesson_if_not_exists(
                        recurring_lesson, current_date, check_conflicts, dry_run
                    )
                    if result["created"]:
                        created += 1
                        if result.get("lesson"):
                            if dry_run:
                                preview.append(result["lesson"])
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
        }

    @staticmethod
    def _generate_monthly_lessons(
        recurring_lesson: RecurringLesson, end_date: date, check_conflicts: bool, dry_run: bool
    ) -> dict:
        """Generiert monatliche Lessons (gleicher Kalendertag jeden Monat)."""
        active_weekdays = recurring_lesson.get_active_weekdays()
        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": []}

        created = 0
        skipped = 0
        conflicts = []
        preview = []

        # Start with the start date
        current_date = recurring_lesson.start_date
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
                result = RecurringLessonService._create_lesson_if_not_exists(
                    recurring_lesson, current_date, check_conflicts, dry_run
                )
                if result["created"]:
                    created += 1
                    if result.get("lesson"):
                        if dry_run:
                            preview.append(result["lesson"])
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
        }

    @staticmethod
    def _create_lesson_if_not_exists(
        recurring_lesson: RecurringLesson, lesson_date: date, check_conflicts: bool, dry_run: bool
    ) -> dict:
        """Helper method: Creates a lesson if it doesn't exist yet."""
        # Check if a lesson already exists for this day
        existing = Lesson.objects.filter(
            contract=recurring_lesson.contract,
            date=lesson_date,
            start_time=recurring_lesson.start_time,
        ).first()

        if existing:
            return {"created": False, "skipped": True}

        # Create new lesson (without status - will be set automatically)
        lesson = Lesson(
            contract=recurring_lesson.contract,
            date=lesson_date,
            start_time=recurring_lesson.start_time,
            duration_minutes=recurring_lesson.duration_minutes,
            travel_time_before_minutes=recurring_lesson.travel_time_before_minutes,
            travel_time_after_minutes=recurring_lesson.travel_time_after_minutes,
            status="",  # Empty - will be set automatically
            notes=recurring_lesson.notes,
        )

        # Automatic status setting (before saving)
        LessonStatusService.update_status_for_lesson(lesson)

        result = {"created": True, "skipped": False, "lesson": lesson, "conflicts": []}

        if not dry_run:
            lesson.save()
            # Set status again after saving (if necessary)
            LessonStatusService.update_status_for_lesson(lesson)

            # Check conflicts
            if check_conflicts:
                lesson_conflicts = LessonConflictService.check_conflicts(lesson)
                if lesson_conflicts:
                    result["conflicts"] = [
                        {"lesson": lesson, "date": lesson_date, "conflicts": lesson_conflicts}
                    ]

        return result

    @staticmethod
    def preview_lessons(recurring_lesson: RecurringLesson) -> List[Lesson]:
        """
        Gibt eine Vorschau der zu erzeugenden Lessons zurück (ohne Speicherung).

        Args:
            recurring_lesson: Die RecurringLesson-Vorlage

        Returns:
            Liste von Lesson-Instanzen (nicht gespeichert)
        """
        result = RecurringLessonService.generate_lessons(
            recurring_lesson, check_conflicts=False, dry_run=True
        )
        return result.get("preview", [])

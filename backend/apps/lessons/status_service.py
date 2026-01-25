"""
Service for automatically updating lesson statuses based on date/time.
"""

from datetime import datetime, timedelta

from apps.lessons.models import Lesson
from django.db import transaction
from django.utils import timezone


class LessonStatusUpdater:
    """
    Service-Klasse für automatische Status-Aktualisierung von Lessons.

    Setzt Lessons mit Status 'planned' automatisch auf 'taught', sobald
    ihre Endzeit in der Vergangenheit liegt.
    """

    @staticmethod
    def update_status_for_lesson(lesson: Lesson) -> bool:
        """
        Aktualisiert den Status einer einzelnen Lesson basierend auf Datum/Zeit.

        Regeln:
        - Wenn end_datetime < jetzt und Status PLANNED → setze auf TAUGHT
        - Wenn start_datetime >= jetzt und Status leer/None → setze auf PLANNED
        - PAID oder CANCELLED werden NICHT überschrieben

        Args:
            lesson: Die Lesson-Instanz

        Returns:
            True, wenn Status geändert wurde, False sonst
        """
        now = timezone.now()

        # Calculate start_datetime and end_datetime
        start_datetime = timezone.make_aware(datetime.combine(lesson.date, lesson.start_time))
        end_datetime = start_datetime + timedelta(minutes=lesson.duration_minutes)

        # Do not overwrite PAID or CANCELLED status
        if lesson.status in ["paid", "cancelled"]:
            return False

        status_changed = False

        # Past lesson (end_datetime < now) with PLANNED or empty status → TAUGHT
        if end_datetime < now and (
            lesson.status == "planned" or not lesson.status or lesson.status == ""
        ):
            lesson.status = "taught"
            status_changed = True

        # Future lesson (start_datetime >= now) without status → PLANNED
        elif start_datetime >= now and (not lesson.status or lesson.status == ""):
            lesson.status = "planned"
            status_changed = True

        # Save only if lesson is already saved (has PK)
        if status_changed and lesson.pk:
            lesson.save(update_fields=["status", "updated_at"])

        return status_changed

    @staticmethod
    def update_past_lessons_to_taught(now=None) -> int:
        """
        Sets all lessons with status 'planned' to 'taught' whose end time
        is in the past.

        Rules:
        - Only lessons with status 'planned' are updated
        - Lessons with status 'paid' or 'cancelled' are NOT changed
        - End time = start_datetime + duration_minutes (without travel times)

        Args:
            now: Optional datetime object (default: timezone.now())

        Returns:
            Number of updated lessons
        """
        if now is None:
            now = timezone.now()

        # Wrap the entire operation in a transaction, as select_for_update() requires a transaction
        with transaction.atomic():
            # Load all lessons with status 'planned'
            # Use select_for_update for thread-safety (optional, but clean)
            lessons = Lesson.objects.filter(status="planned").select_for_update(skip_locked=True)

            updated_lessons = []

            for lesson in lessons:
                # Calculate end_datetime (only lesson duration, without travel times)
                start_datetime = timezone.make_aware(
                    datetime.combine(lesson.date, lesson.start_time)
                )
                end_datetime = start_datetime + timedelta(minutes=lesson.duration_minutes)

                # If end time is in the past, mark for update
                if end_datetime < now:
                    lesson.status = "taught"
                    updated_lessons.append(lesson)

            # Bulk update for performance
            if updated_lessons:
                Lesson.objects.bulk_update(
                    updated_lessons, fields=["status", "updated_at"], batch_size=100
                )

        return len(updated_lessons)


# Alias for backwards compatibility
LessonStatusService = LessonStatusUpdater

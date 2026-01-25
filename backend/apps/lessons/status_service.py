"""
Service für automatische Status-Setzung von Lessons basierend auf Datum/Zeit.
"""

import json
from datetime import datetime, timedelta

from apps.lessons.models import Lesson
from django.db import connection, transaction
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

        # Berechne start_datetime und end_datetime
        start_datetime = timezone.make_aware(datetime.combine(lesson.date, lesson.start_time))
        end_datetime = start_datetime + timedelta(minutes=lesson.duration_minutes)

        # Status PAID oder CANCELLED nicht überschreiben
        if lesson.status in ["paid", "cancelled"]:
            return False

        status_changed = False

        # Vergangene Lesson (end_datetime < jetzt) mit Status PLANNED oder leer → TAUGHT
        if end_datetime < now and (
            lesson.status == "planned" or not lesson.status or lesson.status == ""
        ):
            lesson.status = "taught"
            status_changed = True

        # Zukünftige Lesson (start_datetime >= jetzt) ohne Status → PLANNED
        elif start_datetime >= now and (not lesson.status or lesson.status == ""):
            lesson.status = "planned"
            status_changed = True

        # Speichern nur, wenn Lesson bereits gespeichert ist (hat PK)
        if status_changed and lesson.pk:
            lesson.save(update_fields=["status", "updated_at"])

        return status_changed

    @staticmethod
    def update_past_lessons_to_taught(now=None) -> int:
        """
        Setzt alle Lessons mit Status 'planned' auf 'taught', deren Endzeit
        in der Vergangenheit liegt.

        Regeln:
        - Nur Lessons mit Status 'planned' werden aktualisiert
        - Lessons mit Status 'paid' oder 'cancelled' werden NICHT verändert
        - Endzeit = start_datetime + duration_minutes (ohne Fahrtzeiten)

        Args:
            now: Optional datetime-Objekt (default: timezone.now(), Europe/Berlin)

        Returns:
            Anzahl der aktualisierten Lessons
        """
        if now is None:
            now = timezone.now()

        # #region agent log
        try:
            with open("/Users/eirichandreas/Documents/tutorflow/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "post-fix",
                            "hypothesisId": "A",
                            "location": "status_service.py:84",
                            "message": "Function entry",
                            "data": {
                                "now": str(now),
                                "in_atomic_block": connection.in_atomic_block,
                            },
                            "timestamp": int(timezone.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        # Wrappe die gesamte Operation in eine Transaktion, da select_for_update() eine Transaktion benötigt
        with transaction.atomic():
            # #region agent log
            try:
                with open("/Users/eirichandreas/Documents/tutorflow/.cursor/debug.log", "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "post-fix",
                                "hypothesisId": "A",
                                "location": "status_service.py:90",
                                "message": "Inside transaction atomic block",
                                "data": {
                                    "in_atomic_block": connection.in_atomic_block,
                                    "autocommit": connection.get_autocommit(),
                                },
                                "timestamp": int(timezone.now().timestamp() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion

            # Lade alle Lessons mit Status 'planned'
            # Verwende select_for_update für Thread-Safety (optional, aber sauber)
            lessons = Lesson.objects.filter(status="planned").select_for_update(skip_locked=True)

            updated_lessons = []

            # #region agent log
            try:
                with open("/Users/eirichandreas/Documents/tutorflow/.cursor/debug.log", "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "post-fix",
                                "hypothesisId": "B",
                                "location": "status_service.py:97",
                                "message": "Before iteration",
                                "data": {
                                    "in_atomic_block": connection.in_atomic_block,
                                    "autocommit": connection.get_autocommit(),
                                },
                                "timestamp": int(timezone.now().timestamp() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            for lesson in lessons:
                # Berechne end_datetime (nur Lesson-Dauer, ohne Fahrtzeiten)
                start_datetime = timezone.make_aware(
                    datetime.combine(lesson.date, lesson.start_time)
                )
                end_datetime = start_datetime + timedelta(minutes=lesson.duration_minutes)

                # Wenn Endzeit in der Vergangenheit liegt, markiere zum Update
                if end_datetime < now:
                    lesson.status = "taught"
                    updated_lessons.append(lesson)

            # Bulk-Update für Performance
            if updated_lessons:
                Lesson.objects.bulk_update(
                    updated_lessons, fields=["status", "updated_at"], batch_size=100
                )

        # #region agent log
        try:
            with open("/Users/eirichandreas/Documents/tutorflow/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "post-fix",
                            "hypothesisId": "A",
                            "location": "status_service.py:114",
                            "message": "Function exit",
                            "data": {"updated_count": len(updated_lessons)},
                            "timestamp": int(timezone.now().timestamp() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        return len(updated_lessons)


# Alias für Rückwärtskompatibilität
LessonStatusService = LessonStatusUpdater

"""
Service für wiederholende Blockzeiten (Recurring Blocked Times).
"""

from datetime import date, datetime, timedelta
from typing import List

from apps.blocked_times.models import BlockedTime
from apps.blocked_times.recurring_models import RecurringBlockedTime
from django.utils import timezone
from django.utils.translation import gettext as _


class RecurringBlockedTimeService:
    """Service für die Generierung von BlockedTime-Einträgen aus RecurringBlockedTime-Vorlagen."""

    @staticmethod
    def generate_blocked_times(
        recurring_blocked_time: RecurringBlockedTime,
        check_conflicts: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """
        Generiert BlockedTime-Einträge für eine RecurringBlockedTime über den Zeitraum [start_date, end_date].

        Args:
            recurring_blocked_time: Die RecurringBlockedTime-Vorlage
            check_conflicts: Ob Konflikte geprüft werden sollen (z. B. mit Lessons)
            dry_run: Wenn True, werden keine BlockedTime-Einträge gespeichert, nur Vorschau

        Returns:
            Dict mit:
            - 'created': Anzahl erstellter BlockedTime-Einträge
            - 'skipped': Anzahl übersprungener (bereits vorhandene)
            - 'conflicts': Liste von Konflikten (wenn check_conflicts=True)
            - 'preview': Liste von BlockedTime-Instanzen (wenn dry_run=True)
        """
        if not recurring_blocked_time.is_active:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": []}

        # Bestimme Enddatum
        end_date = recurring_blocked_time.end_date
        if not end_date:
            # Falls kein Enddatum, verwende 1 Jahr nach Start
            end_date = date(
                recurring_blocked_time.start_date.year + 1,
                recurring_blocked_time.start_date.month,
                recurring_blocked_time.start_date.day,
            )

        # Generiere BlockedTime-Einträge basierend auf recurrence_type
        recurrence_type = recurring_blocked_time.recurrence_type

        if recurrence_type == "weekly":
            return RecurringBlockedTimeService._generate_weekly_blocked_times(
                recurring_blocked_time, end_date, check_conflicts, dry_run
            )
        elif recurrence_type == "biweekly":
            return RecurringBlockedTimeService._generate_biweekly_blocked_times(
                recurring_blocked_time, end_date, check_conflicts, dry_run
            )
        elif recurrence_type == "monthly":
            return RecurringBlockedTimeService._generate_monthly_blocked_times(
                recurring_blocked_time, end_date, check_conflicts, dry_run
            )
        else:
            # Fallback auf weekly für unbekannte Typen
            return RecurringBlockedTimeService._generate_weekly_blocked_times(
                recurring_blocked_time, end_date, check_conflicts, dry_run
            )

    @staticmethod
    def _generate_weekly_blocked_times(
        recurring_blocked_time: RecurringBlockedTime,
        end_date: date,
        check_conflicts: bool,
        dry_run: bool,
    ) -> dict:
        """Generiert wöchentliche BlockedTime-Einträge."""
        active_weekdays = recurring_blocked_time.get_active_weekdays()
        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": []}

        current_date = recurring_blocked_time.start_date
        created = 0
        skipped = 0
        conflicts = []
        preview = []

        while current_date <= end_date:
            weekday = current_date.weekday()  # 0=Montag, 6=Sonntag

            if weekday in active_weekdays:
                result = RecurringBlockedTimeService._create_blocked_time_if_not_exists(
                    recurring_blocked_time, current_date, check_conflicts, dry_run
                )
                if result["created"]:
                    created += 1
                    if result.get("blocked_time"):
                        if dry_run:
                            preview.append(result["blocked_time"])
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
    def _generate_biweekly_blocked_times(
        recurring_blocked_time: RecurringBlockedTime,
        end_date: date,
        check_conflicts: bool,
        dry_run: bool,
    ) -> dict:
        """Generiert zweiwöchentliche BlockedTime-Einträge (alle 2 Wochen)."""
        active_weekdays = recurring_blocked_time.get_active_weekdays()
        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": []}

        current_date = recurring_blocked_time.start_date
        created = 0
        skipped = 0
        conflicts = []
        preview = []

        # Zähle Wochen seit Start
        week_count = 0

        while current_date <= end_date:
            weekday = current_date.weekday()

            if weekday in active_weekdays:
                # Nur jede 2. Woche (gerade Wochennummer)
                if week_count % 2 == 0:
                    result = RecurringBlockedTimeService._create_blocked_time_if_not_exists(
                        recurring_blocked_time, current_date, check_conflicts, dry_run
                    )
                    if result["created"]:
                        created += 1
                        if result.get("blocked_time"):
                            if dry_run:
                                preview.append(result["blocked_time"])
                            if result.get("conflicts"):
                                conflicts.extend(result["conflicts"])
                    elif result["skipped"]:
                        skipped += 1

            # Wenn wir einen Montag erreichen, erhöhe Wochenzähler
            if weekday == 0:  # Montag
                week_count += 1

            current_date += timedelta(days=1)

        return {
            "created": created,
            "skipped": skipped,
            "conflicts": conflicts,
            "preview": preview if dry_run else [],
        }

    @staticmethod
    def _generate_monthly_blocked_times(
        recurring_blocked_time: RecurringBlockedTime,
        end_date: date,
        check_conflicts: bool,
        dry_run: bool,
    ) -> dict:
        """Generiert monatliche BlockedTime-Einträge (gleicher Kalendertag jeden Monat)."""
        active_weekdays = recurring_blocked_time.get_active_weekdays()
        if not active_weekdays:
            return {"created": 0, "skipped": 0, "conflicts": [], "preview": []}

        created = 0
        skipped = 0
        conflicts = []
        preview = []

        # Starte mit dem Startdatum
        current_date = recurring_blocked_time.start_date
        start_day = current_date.day  # Tag des Monats (z.B. 15.)

        from calendar import monthrange

        while current_date <= end_date:
            # Prüfe, ob aktuelles Datum der richtige Tag des Monats ist
            # UND ob es ein aktiver Wochentag ist
            target_day = start_day
            # Wenn der Tag im aktuellen Monat nicht existiert (z.B. 31. Februar),
            # verwende den letzten Tag des Monats
            last_day_of_month = monthrange(current_date.year, current_date.month)[1]
            if start_day > last_day_of_month:
                target_day = last_day_of_month

            if current_date.day == target_day and current_date.weekday() in active_weekdays:
                result = RecurringBlockedTimeService._create_blocked_time_if_not_exists(
                    recurring_blocked_time, current_date, check_conflicts, dry_run
                )
                if result["created"]:
                    created += 1
                    if result.get("blocked_time"):
                        if dry_run:
                            preview.append(result["blocked_time"])
                        if result.get("conflicts"):
                            conflicts.extend(result["conflicts"])
                elif result["skipped"]:
                    skipped += 1

            # Springe zum nächsten Monat
            # Berechne den nächsten Monat
            if current_date.month == 12:
                next_year = current_date.year + 1
                next_month = 1
            else:
                next_year = current_date.year
                next_month = current_date.month + 1

            # Versuche denselben Tag im nächsten Monat
            last_day_next_month = monthrange(next_year, next_month)[1]
            target_day_next = min(start_day, last_day_next_month)

            try:
                current_date = date(next_year, next_month, target_day_next)
            except ValueError:
                # Fallback: letzter Tag des Monats
                current_date = date(next_year, next_month, last_day_next_month)

        return {
            "created": created,
            "skipped": skipped,
            "conflicts": conflicts,
            "preview": preview if dry_run else [],
        }

    @staticmethod
    def _create_blocked_time_if_not_exists(
        recurring_blocked_time: RecurringBlockedTime,
        blocked_date: date,
        check_conflicts: bool,
        dry_run: bool,
    ) -> dict:
        """Hilfsmethode: Erstellt einen BlockedTime-Eintrag, falls er noch nicht existiert."""
        # Kombiniere Datum mit Start- und Endzeit
        start_datetime = timezone.make_aware(
            datetime.combine(blocked_date, recurring_blocked_time.start_time)
        )
        end_datetime = timezone.make_aware(
            datetime.combine(blocked_date, recurring_blocked_time.end_time)
        )

        # Prüfe, ob bereits ein BlockedTime-Eintrag für diesen Zeitraum existiert
        existing = BlockedTime.objects.filter(
            title=recurring_blocked_time.title,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        ).first()

        if existing:
            return {"created": False, "skipped": True}

        # Erstelle neuen BlockedTime-Eintrag
        blocked_time = BlockedTime(
            user=recurring_blocked_time.user,
            title=recurring_blocked_time.title,
            description=recurring_blocked_time.description,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            is_recurring=True,
            recurring_pattern=recurring_blocked_time.recurrence_type,
        )

        result = {"created": True, "skipped": False, "blocked_time": blocked_time, "conflicts": []}

        if not dry_run:
            blocked_time.save()

            # Prüfe Konflikte mit Lessons (falls gewünscht) - nur Lessons desselben Users
            if check_conflicts:
                from apps.lessons.models import Lesson
                from apps.lessons.services import LessonConflictService

                # Finde alle Lessons desselben Users, die mit dieser Blockzeit kollidieren
                conflicting_lessons = Lesson.objects.filter(
                    date=blocked_date, contract__student__user=recurring_blocked_time.user
                ).select_related("contract", "contract__student")

                for lesson in conflicting_lessons:
                    lesson_start, lesson_end = LessonConflictService.calculate_time_block(lesson)
                    # Prüfe Überlappung
                    if not (end_datetime <= lesson_start or start_datetime >= lesson_end):
                        result["conflicts"].append(
                            {
                                "lesson": lesson,
                                "date": blocked_date,
                                "message": _("Overlap with lesson for {student} ({time})").format(
                                    student=lesson.contract.student,
                                    time=lesson.start_time.strftime("%H:%M"),
                                ),
                            }
                        )

        return result

    @staticmethod
    def preview_blocked_times(recurring_blocked_time: RecurringBlockedTime) -> List[BlockedTime]:
        """
        Gibt eine Vorschau der zu erzeugenden BlockedTime-Einträge zurück (ohne Speicherung).

        Args:
            recurring_blocked_time: Die RecurringBlockedTime-Vorlage

        Returns:
            Liste von BlockedTime-Instanzen (nicht gespeichert)
        """
        result = RecurringBlockedTimeService.generate_blocked_times(
            recurring_blocked_time, check_conflicts=False, dry_run=True
        )
        return result.get("preview", [])

"""
Management command to detect and fix RecurringLesson records whose
start_time or weekday fields don't match the majority of their generated sessions.

Usage:
  python manage.py fix_recurring_mismatch           # dry run – show mismatches
  python manage.py fix_recurring_mismatch --fix     # apply corrections to DB
"""

from collections import Counter

from django.core.management.base import BaseCommand

from apps.lessons.recurring_models import RecurringSession


class Command(BaseCommand):
    help = "Detect and optionally fix recurring lessons whose data mismatches their sessions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Apply corrections (default: dry run only)",
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        fixed = 0
        mismatches = 0

        for recurring in RecurringSession.objects.prefetch_related("generated_sessions").all():
            sessions = list(recurring.generated_sessions.all())
            if not sessions:
                continue

            # Determine the dominant start_time among sessions
            time_counts = Counter(s.start_time for s in sessions)
            dominant_time = time_counts.most_common(1)[0][0]

            # Determine the dominant weekday(s) among sessions
            weekday_counts = Counter(s.date.weekday() for s in sessions)
            dominant_weekdays = {
                wd for wd, cnt in weekday_counts.items() if cnt >= len(sessions) * 0.4
            }

            current_time_ok = recurring.start_time == dominant_time
            current_weekdays = set(recurring.get_active_weekdays())
            current_weekdays_ok = bool(current_weekdays & dominant_weekdays)

            if current_time_ok and current_weekdays_ok:
                continue

            mismatches += 1
            self.stdout.write(
                self.style.WARNING(
                    f"MISMATCH: RecurringLesson #{recurring.pk} "
                    f"({recurring.contract.student}) "
                    f"— template: {recurring.get_active_weekdays_display()} {recurring.start_time} "
                    f"— sessions dominant: weekday(s)={sorted(dominant_weekdays)} "
                    f"time={dominant_time} "
                    f"(sample size: {len(sessions)})"
                )
            )

            if fix:
                # Update start_time
                recurring.start_time = dominant_time

                # Update weekday booleans
                recurring.monday = 0 in dominant_weekdays
                recurring.tuesday = 1 in dominant_weekdays
                recurring.wednesday = 2 in dominant_weekdays
                recurring.thursday = 3 in dominant_weekdays
                recurring.friday = 4 in dominant_weekdays
                recurring.saturday = 5 in dominant_weekdays
                recurring.sunday = 6 in dominant_weekdays

                recurring.save()
                fixed += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  → Fixed: set to "
                        f"{recurring.get_active_weekdays_display()} {recurring.start_time}"
                    )
                )

        if mismatches == 0:
            self.stdout.write(self.style.SUCCESS("No mismatches found."))
        elif not fix:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{mismatches} mismatch(es) found. Run with --fix to apply corrections."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n{fixed}/{mismatches} recurring lesson(s) corrected.")
            )

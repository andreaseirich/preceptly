"""
One-off: Mark lessons 0006, 0007, 0008 as applied so history matches billing.0001.

Use when the DB has billing.0001_initial applied before lessons.0008 (wrong order).
Run once, then run: python manage.py migrate
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

# In dependency order so each is after its deps (0001..0008 for billing.0001 dependency)
LESSONS_TO_RECORD = [
    "0001_initial",
    "0002_recurringlesson",
    "0003_recurringlesson_recurrence_type",
    "0004_alter_lesson_options_alter_recurringlesson_options_and_more",
    "0005_lessondocument",
    "0006_create_lessons_lesson_table_if_missing",
    "0007_session_created_via",
    "0008_rename_lesson_to_session_state",
]


class Command(BaseCommand):
    help = "Mark lessons.0006–0008 as applied (fix InconsistentMigrationHistory with billing.0001)"

    def handle(self, *args, **options):
        recorder = MigrationRecorder(connection)
        recorded = []
        for name in LESSONS_TO_RECORD:
            if recorder.migration_qs.filter(app="lessons", name=name).exists():
                continue
            recorder.record_applied("lessons", name)
            recorded.append(name)
        if recorded:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recorded as applied: {', '.join(recorded)}. Run: python manage.py migrate"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("All of lessons.0006–0008 were already recorded."))

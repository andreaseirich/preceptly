# Sync migration state: Lesson->Session, LessonDocument->SessionDocument,
# RecurringLesson->RecurringSession. Database unchanged (same tables via db_table).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0007_session_created_via"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameModel(old_name="Lesson", new_name="Session"),
                migrations.AlterModelTable(name="Session", table="lessons_lesson"),
                migrations.AlterField(
                    model_name="session",
                    name="contract",
                    field=models.ForeignKey(
                        help_text="Associated contract",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to="contracts.contract",
                    ),
                ),
                migrations.RenameModel(old_name="LessonDocument", new_name="SessionDocument"),
                migrations.AlterModelTable(name="SessionDocument", table="lessons_lessondocument"),
                migrations.RenameField(
                    model_name="sessiondocument",
                    old_name="lesson",
                    new_name="session",
                ),
                migrations.AlterField(
                    model_name="sessiondocument",
                    name="session",
                    field=models.ForeignKey(
                        db_column="lesson_id",
                        help_text="Associated session",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="lessons.session",
                    ),
                ),
                migrations.RenameModel(old_name="RecurringLesson", new_name="RecurringSession"),
                migrations.AlterModelTable(name="RecurringSession", table="lessons_recurringlesson"),
                migrations.AlterField(
                    model_name="recurringsession",
                    name="contract",
                    field=models.ForeignKey(
                        help_text="Associated contract",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recurring_sessions",
                        to="contracts.contract",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

# Update FK to point to lessons.Session (same table as Lesson). State only.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lesson_plans", "0002_alter_lessonplan_options_alter_lessonplan_content_and_more"),
        ("lessons", "0008_rename_lesson_to_session_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="lessonplan",
                    name="lesson",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="lesson_id",
                        help_text="Associated session (optional)",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lesson_plans",
                        to="lessons.session",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

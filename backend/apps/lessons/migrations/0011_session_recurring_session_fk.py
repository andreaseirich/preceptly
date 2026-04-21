"""Add recurring_session FK to Session for reliable series deletion."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lessons", "0010_session_tutor_no_show"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="recurring_session",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="generated_sessions",
                to="lessons.recurringsession",
                help_text="Recurring series this session was generated from",
            ),
        ),
    ]

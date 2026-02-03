# Generated for Premium public booking limit

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0006_create_lessons_lesson_table_if_missing"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="created_via",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Source: public_booking, contract_booking, or tutor",
                max_length=20,
                null=True,
            ),
        ),
    ]

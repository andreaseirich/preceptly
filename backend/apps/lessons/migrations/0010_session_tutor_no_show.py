# Generated manually for tutor no-show flag on session

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lessons", "0009_alter_recurringsession_options_alter_session_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="tutor_no_show",
            field=models.BooleanField(
                default=False,
                help_text="Tutor did not attend while the student was waiting (affects TutorSpace compensation per your settings).",
            ),
        ),
    ]

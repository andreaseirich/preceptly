from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0007_institutetierconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="is_adult",
            field=models.BooleanField(
                default=False,
                verbose_name="Erwachsener Schüler",
                help_text="Wenn aktiviert, wird kein Eltern-Portal-Zugang angeboten.",
            ),
        ),
    ]

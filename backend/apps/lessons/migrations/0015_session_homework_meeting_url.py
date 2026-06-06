from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0014_add_contract_date_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="homework",
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name="Homework",
                help_text="Homework assigned for next session",
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="meeting_url",
            field=models.CharField(
                max_length=500,
                blank=True,
                null=True,
                verbose_name="Meeting URL",
                help_text="Zoom/Meet link for this session",
            ),
        ),
    ]

# Generated manually for multi-tenancy

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_userprofile_default_working_hours"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="public_booking_token",
            field=models.CharField(
                blank=True,
                help_text="Token for public booking URL (e.g. /public-booking/<token>/)",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]

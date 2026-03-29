# TutorSpace: optional start date for tier cumulative minutes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_userprofile_tutor_no_show_pay_percent"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="tutorspace_tier_count_from",
            field=models.DateField(
                blank=True,
                help_text=(
                    "If set, only TutorSpace sessions on or after this date count toward "
                    "13/14 € hour tiers. Leave empty to count all past sessions (global)."
                ),
                null=True,
            ),
        ),
    ]

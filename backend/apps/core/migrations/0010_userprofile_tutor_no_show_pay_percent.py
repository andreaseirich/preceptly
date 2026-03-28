# Generated manually for tutor no-show pay percent

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_userprofile_travel_policy_booking_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="tutor_no_show_pay_percent",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="For TutorSpace: when a session is marked 'tutor did not show (student waited)', pay this percentage of the calculated amount (0 = no pay, 100 = full pay).",
            ),
        ),
    ]

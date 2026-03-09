# Travel policy for on-site booking (time-dependent ÖPNV buffer + no-go windows)

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_userprofile_stripe_email_last_synced"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="travel_policy",
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text=(
                    "Time-dependent travel policy for vor_ort booking: "
                    "{'enabled': bool, 'buffer_rules': [{'weekday': 0-6, 'start_time': 'HH:MM', 'end_time': 'HH:MM', 'buffer_minutes': int}], "
                    "'no_go_windows': [{'weekday': 0-6, 'start_time': 'HH:MM', 'end_time': 'HH:MM'}]}. "
                    "Weekday 0=Monday, 6=Sunday."
                ),
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="default_booking_location",
            field=models.CharField(
                max_length=20,
                choices=[("online", "Online"), ("vor_ort", "Vor Ort")],
                default="online",
                help_text="Default appointment type for public booking; vor_ort applies travel policy.",
            ),
        ),
    ]

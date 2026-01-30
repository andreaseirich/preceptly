# Make user field required after data migration

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blocked_times", "0005_assign_blocked_times_to_first_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="blockedtime",
            name="user",
            field=models.ForeignKey(
                help_text="User who owns this blocked time",
                on_delete=models.CASCADE,
                related_name="blocked_times",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="recurringblockedtime",
            name="user",
            field=models.ForeignKey(
                help_text="User who owns this recurring blocked time",
                on_delete=models.CASCADE,
                related_name="recurring_blocked_times",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

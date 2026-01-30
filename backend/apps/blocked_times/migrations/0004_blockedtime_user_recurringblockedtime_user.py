# Generated manually for multi-tenancy

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("blocked_times", "0003_alter_blockedtime_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="blockedtime",
            name="user",
            field=models.ForeignKey(
                help_text="User who owns this blocked time",
                null=True,
                blank=True,
                on_delete=models.CASCADE,
                related_name="blocked_times",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="recurringblockedtime",
            name="user",
            field=models.ForeignKey(
                help_text="User who owns this recurring blocked time",
                null=True,
                blank=True,
                on_delete=models.CASCADE,
                related_name="recurring_blocked_times",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

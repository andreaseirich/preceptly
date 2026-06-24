# Generated manually: drop RecurringBlockedTime table

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blocked_times", "0007_migrate_recurring_to_blockedtime"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(
            name="RecurringBlockedTime",
        ),
    ]

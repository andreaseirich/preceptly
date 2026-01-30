# Data migration: Assign existing blocked times to first user

from django.db import migrations


def assign_to_user(apps, schema_editor):
    """Assign all BlockedTime and RecurringBlockedTime without user to the first user."""
    BlockedTime = apps.get_model("blocked_times", "BlockedTime")
    RecurringBlockedTime = apps.get_model("blocked_times", "RecurringBlockedTime")
    User = apps.get_model("auth", "User")

    needs_user = (
        BlockedTime.objects.filter(user__isnull=True).exists()
        or RecurringBlockedTime.objects.filter(user__isnull=True).exists()
    )
    if not needs_user:
        return

    first_user = User.objects.order_by("id").first()
    if not first_user:
        raise RuntimeError(
            "Multi-tenancy migration requires at least one user. "
            "Please create a user first, then run migrate again."
        )
    BlockedTime.objects.filter(user__isnull=True).update(user=first_user)
    RecurringBlockedTime.objects.filter(user__isnull=True).update(user=first_user)


def reverse_assign(apps, schema_editor):
    """Reverse: set user to null."""
    BlockedTime = apps.get_model("blocked_times", "BlockedTime")
    RecurringBlockedTime = apps.get_model("blocked_times", "RecurringBlockedTime")
    BlockedTime.objects.all().update(user=None)
    RecurringBlockedTime.objects.all().update(user=None)


class Migration(migrations.Migration):
    dependencies = [
        ("blocked_times", "0004_blockedtime_user_recurringblockedtime_user"),
    ]

    operations = [
        migrations.RunPython(assign_to_user, reverse_assign),
    ]

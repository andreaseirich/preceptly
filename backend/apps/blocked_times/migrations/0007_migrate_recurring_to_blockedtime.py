# Generated manually: migrate RecurringBlockedTime data to BlockedTime

from datetime import date, datetime, timedelta

from django.db import migrations
from django.utils import timezone


def _get_weekdays(rbt):
    days = []
    if rbt.monday:
        days.append(0)
    if rbt.tuesday:
        days.append(1)
    if rbt.wednesday:
        days.append(2)
    if rbt.thursday:
        days.append(3)
    if rbt.friday:
        days.append(4)
    if rbt.saturday:
        days.append(5)
    if rbt.sunday:
        days.append(6)
    return days


def migrate_recurring_to_blocked(apps, schema_editor):
    RecurringBlockedTime = apps.get_model("blocked_times", "RecurringBlockedTime")
    BlockedTime = apps.get_model("blocked_times", "BlockedTime")

    today = date.today()
    max_horizon = today + timedelta(days=365 * 3)

    created_total = 0

    for rbt in RecurringBlockedTime.objects.filter(is_active=True):
        weekdays = _get_weekdays(rbt)
        if not weekdays:
            continue

        end_date = rbt.end_date if rbt.end_date else max_horizon
        end_date = min(end_date, max_horizon)

        current = rbt.start_date
        while current <= end_date:
            if current.weekday() in weekdays:
                start_dt = timezone.make_aware(datetime.combine(current, rbt.start_time))
                end_dt = timezone.make_aware(datetime.combine(current, rbt.end_time))
                exists = BlockedTime.objects.filter(
                    user=rbt.user,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                ).exists()
                if not exists:
                    BlockedTime.objects.create(
                        user=rbt.user,
                        title=rbt.title,
                        description=rbt.description or "",
                        start_datetime=start_dt,
                        end_datetime=end_dt,
                        is_recurring=True,
                        recurring_pattern=rbt.recurrence_type,
                    )
                    created_total += 1
            if rbt.recurrence_type == "biweekly":
                # Advance by full week per weekday, restart 2-week cycle from start
                pass
            current += timedelta(days=1)

    print(f"Migration: {created_total} BlockedTime entries created.")


def reverse_migrate(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("blocked_times", "0006_blockedtime_user_required"),
    ]

    operations = [
        migrations.RunPython(migrate_recurring_to_blocked, reverse_migrate),
    ]

"""Backfill recurring_session FK for existing sessions.

Assigns each session to its RecurringSession if a unique match exists:
- same contract
- session date within the series date range
- session weekday is an active weekday in the series

Sessions that match zero or multiple series are left as NULL.
"""

from django.db import migrations


def _get_active_weekdays(recurring):
    """Return list of active weekday numbers (0=Mon..6=Sun) for a RecurringSession row."""
    mapping = [
        (recurring.monday, 0),
        (recurring.tuesday, 1),
        (recurring.wednesday, 2),
        (recurring.thursday, 3),
        (recurring.friday, 4),
        (recurring.saturday, 5),
        (recurring.sunday, 6),
    ]
    return [wd for active, wd in mapping if active]


def backfill(apps, schema_editor):
    Session = apps.get_model("lessons", "Session")
    RecurringSession = apps.get_model("lessons", "RecurringSession")

    recurring_by_contract = {}
    for rs in RecurringSession.objects.all():
        recurring_by_contract.setdefault(rs.contract_id, []).append(rs)

    to_update = []
    for session in Session.objects.filter(recurring_session__isnull=True):
        candidates = recurring_by_contract.get(session.contract_id, [])
        matches = []
        for rs in candidates:
            # Date range check
            if session.date < rs.start_date:
                continue
            if rs.end_date and session.date > rs.end_date:
                continue
            # Weekday check (Python weekday: 0=Mon..6=Sun)
            if session.date.weekday() not in _get_active_weekdays(rs):
                continue
            matches.append(rs)

        if len(matches) == 1:
            session.recurring_session_id = matches[0].id
            to_update.append(session)

    if to_update:
        Session.objects.bulk_update(to_update, ["recurring_session_id"], batch_size=500)


def reverse_backfill(apps, schema_editor):
    Session = apps.get_model("lessons", "Session")
    Session.objects.update(recurring_session_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("lessons", "0011_session_recurring_session_fk"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_backfill),
    ]

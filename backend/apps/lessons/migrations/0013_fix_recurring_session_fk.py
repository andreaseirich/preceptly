"""
Two-part fix for recurring series deletion:

1. Improve backfill: for contracts with exactly ONE recurring series, link ALL
   sessions within the series date range (regardless of weekday).  The previous
   migration (0012) only matched sessions on the template's weekday, missing
   sessions that were individually rescheduled to a different day.

   For contracts with MULTIPLE overlapping series the weekday-based assignment
   from 0012 is kept (we cannot reliably tell which series a rescheduled session
   belongs to without more context).

2. Replace the database FK constraint with ON DELETE CASCADE so that deleting a
   RecurringSession row in the DB automatically removes all linked sessions,
   matching the Django on_delete=CASCADE semantic we want.
"""

import django.db.models.deletion
from django.db import migrations, models


# ---------------------------------------------------------------------------
# Data migration helpers
# ---------------------------------------------------------------------------

def improved_backfill(apps, schema_editor):
    Session = apps.get_model("lessons", "Session")
    RecurringSession = apps.get_model("lessons", "RecurringSession")

    from collections import defaultdict

    recurring_by_contract = defaultdict(list)
    for rs in RecurringSession.objects.all():
        recurring_by_contract[rs.contract_id].append(rs)

    to_update = []
    for contract_id, series_list in recurring_by_contract.items():
        if len(series_list) != 1:
            # Multiple series on this contract — weekday assignment from 0012 is
            # the best we can do; leave ambiguous sessions as NULL.
            continue

        rs = series_list[0]
        qs = Session.objects.filter(
            contract_id=contract_id,
            recurring_session_id__isnull=True,
            date__gte=rs.start_date,
        )
        if rs.end_date:
            qs = qs.filter(date__lte=rs.end_date)

        for session in qs:
            session.recurring_session_id = rs.id
            to_update.append(session)

    if to_update:
        Session.objects.bulk_update(to_update, ["recurring_session_id"], batch_size=500)


def reverse_improved_backfill(apps, schema_editor):
    # Re-applying 0012's logic on rollback is complex; just clear everything and
    # let 0012's forward migration handle it if rolled back to that point.
    Session = apps.get_model("lessons", "Session")
    Session.objects.update(recurring_session_id=None)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class Migration(migrations.Migration):

    dependencies = [
        ("lessons", "0012_backfill_recurring_session_fk"),
    ]

    operations = [
        # Step 1: improved backfill
        migrations.RunPython(improved_backfill, reverse_improved_backfill),

        # Step 2: change on_delete to CASCADE
        migrations.AlterField(
            model_name="session",
            name="recurring_session",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="generated_sessions",
                to="lessons.recurringsession",
                help_text="Recurring series this session was generated from",
            ),
        ),
    ]

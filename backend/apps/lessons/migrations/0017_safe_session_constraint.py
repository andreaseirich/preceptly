from django.db import migrations, models
from django.db.models import Q


def fix_session_no_show(apps, schema_editor):
    Session = apps.get_model("lessons", "Session")
    count = Session.objects.filter(
        tutor_no_show=True,
        status__in=["cancelled", "paid"],
    ).update(tutor_no_show=False)
    if count:
        print(f"  Fixed {count} sessions with inconsistent tutor_no_show + status")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0016_alter_session_tutor_no_show"),
    ]

    operations = [
        migrations.RunPython(fix_session_no_show, noop),
        migrations.AddConstraint(
            model_name="session",
            constraint=models.CheckConstraint(
                condition=~Q(status__in=["cancelled", "paid"]) | Q(tutor_no_show=False),
                name="session_no_show_only_if_not_cancelled_paid",
            ),
        ),
    ]

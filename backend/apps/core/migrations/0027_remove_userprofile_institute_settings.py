from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0026_revocationrequest"),
        ("contracts", "0019_backfill_institute_fk"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="tutor_no_show_pay_percent",
        ),
        migrations.RemoveField(
            model_name="userprofile",
            name="tutorspace_tier_count_from",
        ),
    ]

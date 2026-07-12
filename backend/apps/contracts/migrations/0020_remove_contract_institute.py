from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0019_backfill_institute_fk"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="contract",
            name="institute",
        ),
    ]

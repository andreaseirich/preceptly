from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0013_fix_recurring_session_fk"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="session",
            index=models.Index(fields=["contract", "date"], name="lessons_les_contract_date_idx"),
        ),
    ]

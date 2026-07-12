import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0017_institute_rename_and_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="institute_fk",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                blank=True,
                related_name="contracts",
                to="contracts.institute",
                verbose_name="institute",
                help_text=(
                    "Institute this contract is billed through, or empty for private lessons."
                ),
            ),
        ),
    ]

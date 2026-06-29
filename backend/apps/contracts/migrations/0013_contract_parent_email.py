from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0012_alter_contract_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="parent_email",
            field=models.EmailField(
                blank=True,
                null=True,
                verbose_name="Eltern-E-Mail",
            ),
        ),
        migrations.AlterField(
            model_name="contract",
            name="email",
            field=models.EmailField(
                blank=True,
                null=True,
                verbose_name="Schüler-E-Mail",
            ),
        ),
    ]

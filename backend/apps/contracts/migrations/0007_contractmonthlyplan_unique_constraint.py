from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0006_contract_booking_token_working_hours"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="contractmonthlyplan",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="contractmonthlyplan",
            constraint=models.UniqueConstraint(
                fields=["contract", "year", "month"],
                name="unique_contract_year_month",
            ),
        ),
    ]

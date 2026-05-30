from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_expense"),
    ]

    operations = [
        migrations.AddField(
            model_name="expense",
            name="business_use_percent",
            field=models.PositiveSmallIntegerField(
                default=100,
                help_text="Percentage of this expense used for business purposes (1\u2013100).",
                verbose_name="Business use (%)",
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
    ]

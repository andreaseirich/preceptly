import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contracts", "0016_tiers_blank_true"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="InstituteTierConfig",
            new_name="Institute",
        ),
        migrations.AlterModelOptions(
            name="institute",
            options={
                "ordering": ["institute_name"],
                "verbose_name": "Institute",
                "verbose_name_plural": "Institutes",
            },
        ),
        migrations.AlterField(
            model_name="institute",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="institutes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="institute",
            name="institute_name",
            field=models.CharField(max_length=200, verbose_name="name"),
        ),
        migrations.AddField(
            model_name="institute",
            name="tutor_no_show_pay_percent",
            field=models.PositiveSmallIntegerField(
                default=0,
                blank=True,
                validators=[django.core.validators.MaxValueValidator(100)],
                verbose_name="pay when you missed the lesson (student was waiting)",
                help_text=(
                    "For this institute, if you mark a lesson as tutor no-show: share of the "
                    "usual lesson pay you keep. Only used when this institute has tiered pay."
                ),
            ),
        ),
        migrations.AddField(
            model_name="institute",
            name="tier_count_from",
            field=models.DateField(
                null=True,
                blank=True,
                verbose_name="count tier hours only from (optional)",
                help_text=(
                    "Empty: every past lesson for this institute counts toward the tiers. Set "
                    "a date if the preview or amounts look wrong because many older lessons "
                    "are included."
                ),
            ),
        ),
    ]

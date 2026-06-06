from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0008_institutetierconfig"),
        ("students", "0009_studentdocument"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contracts",
                to=settings.AUTH_USER_MODEL,
                verbose_name="tutor",
            ),
        ),
        migrations.AddField(
            model_name="contract",
            name="first_name",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="first name"
            ),
        ),
        migrations.AddField(
            model_name="contract",
            name="last_name",
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name="last name"),
        ),
        migrations.AddField(
            model_name="contract",
            name="email",
            field=models.EmailField(blank=True, null=True, verbose_name="email"),
        ),
        migrations.AddField(
            model_name="contract",
            name="phone",
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name="phone"),
        ),
        migrations.AddField(
            model_name="contract",
            name="school",
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name="school"),
        ),
        migrations.AddField(
            model_name="contract",
            name="grade",
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name="grade"),
        ),
        migrations.AddField(
            model_name="contract",
            name="subjects",
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name="subjects"),
        ),
        migrations.AddField(
            model_name="contract",
            name="is_adult",
            field=models.BooleanField(default=False, verbose_name="Erwachsener Schüler"),
        ),
        migrations.AddField(
            model_name="contract",
            name="booking_code_hash",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
    ]

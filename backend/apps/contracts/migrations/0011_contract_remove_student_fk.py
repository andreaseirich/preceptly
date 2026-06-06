from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0010_contract_copy_student_data"),
        ("portal", "0003_portal_contract_fks"),
        ("lesson_plans", "0004_lessonplan_contract_fk"),
        ("students", "0010_studentdocument_contract_fk"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(model_name="contract", name="student"),
        migrations.AlterField(
            model_name="contract",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contracts",
                to=settings.AUTH_USER_MODEL,
                verbose_name="tutor",
            ),
        ),
        migrations.AlterField(
            model_name="contract",
            name="first_name",
            field=models.CharField(max_length=100, verbose_name="first name"),
        ),
        migrations.AlterField(
            model_name="contract",
            name="last_name",
            field=models.CharField(max_length=100, verbose_name="last name"),
        ),
        migrations.AlterModelOptions(
            name="contract",
            options={
                "ordering": ["-start_date", "last_name", "first_name"],
                "verbose_name": "Contract",
                "verbose_name_plural": "Contracts",
            },
        ),
    ]

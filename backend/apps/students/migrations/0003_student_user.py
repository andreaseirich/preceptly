# Generated manually for multi-tenancy

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("students", "0002_alter_student_options_alter_student_grade_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="user",
            field=models.ForeignKey(
                help_text="Tutor who owns this student data",
                null=True,
                blank=True,
                on_delete=models.CASCADE,
                related_name="students",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

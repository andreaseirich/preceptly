# Make user field required after data migration

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0004_assign_students_to_first_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="user",
            field=models.ForeignKey(
                help_text="Tutor who owns this student data",
                on_delete=models.CASCADE,
                related_name="students",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

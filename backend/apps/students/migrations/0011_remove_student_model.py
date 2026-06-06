from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0010_studentdocument_contract_fk"),
        ("contracts", "0011_contract_remove_student_fk"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="Student"),
    ]

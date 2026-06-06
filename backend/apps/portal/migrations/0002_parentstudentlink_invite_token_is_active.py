import uuid

from django.db import migrations, models


def set_default_tokens(apps, schema_editor):
    """Set a unique invite_token for every existing ParentStudentLink."""
    ParentStudentLink = apps.get_model("portal", "ParentStudentLink")
    for link in ParentStudentLink.objects.filter(invite_token=""):
        link.invite_token = uuid.uuid4().hex
        link.save(update_fields=["invite_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentstudentlink",
            name="invite_token",
            field=models.CharField(blank=True, default="", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="parentstudentlink",
            name="is_active",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(set_default_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="parentstudentlink",
            name="invite_token",
            field=models.CharField(blank=True, max_length=64, unique=True),
        ),
    ]

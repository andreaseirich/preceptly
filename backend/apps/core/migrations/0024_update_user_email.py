from django.db import migrations


def update_user_email(apps, schema_editor):
    User = apps.get_model("auth", "User")
    User.objects.filter(email="eirichandreas2004@icloud.com").update(email="contact@andicode.de")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_userprofile_split_billing_contact"),
    ]

    operations = [
        migrations.RunPython(update_user_email, migrations.RunPython.noop),
    ]

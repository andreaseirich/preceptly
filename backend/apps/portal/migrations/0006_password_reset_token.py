from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0005_invite_token_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentportallink",
            name="reset_token",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="studentportallink",
            name="reset_token_created_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="parentstudentlink",
            name="reset_token",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="parentstudentlink",
            name="reset_token_created_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

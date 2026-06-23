# Generated manually 2026-06-23

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_add_userprofile_timezone"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RequestLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("path", models.CharField(max_length=500)),
                ("method", models.CharField(max_length=10)),
                ("status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("session_key", models.CharField(blank=True, max_length=40)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("referer", models.CharField(blank=True, max_length=500)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-timestamp"],
                "indexes": [
                    models.Index(
                        fields=["timestamp", "path"], name="core_reques_timesta_8d05ea_idx"
                    )
                ],
            },
        ),
    ]

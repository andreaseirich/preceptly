import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("lessons", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MeetingRoom",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "lesson",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meeting_room",
                        to="lessons.session",
                        verbose_name="Lesson",
                    ),
                ),
                (
                    "token",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        verbose_name="Room Token",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Meeting Room",
                "verbose_name_plural": "Meeting Rooms",
            },
        ),
    ]

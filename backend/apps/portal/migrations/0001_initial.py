import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("students", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "role",
                    models.CharField(
                        choices=[("parent", "Parent"), ("student", "Student")], max_length=10
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tutor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_users",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name": "Portal User", "verbose_name_plural": "Portal Users"},
        ),
        migrations.CreateModel(
            name="StudentPortalLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("invite_token", models.CharField(blank=True, max_length=64, unique=True)),
                ("is_active", models.BooleanField(default=False)),
                (
                    "portal_user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_link",
                        to="portal.portaluser",
                    ),
                ),
                (
                    "student",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_link",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "verbose_name": "Student Portal Link",
                "verbose_name_plural": "Student Portal Links",
            },
        ),
        migrations.CreateModel(
            name="ParentStudentLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "parent",
                    models.ForeignKey(
                        limit_choices_to={"role": "parent"},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="child_links",
                        to="portal.portaluser",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parent_links",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "unique_together": {("parent", "student")},
                "verbose_name": "Parent-Student Link",
                "verbose_name_plural": "Parent-Student Links",
            },
        ),
        migrations.CreateModel(
            name="ProgressNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("text", models.TextField(verbose_name="Note")),
                ("date", models.DateField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_notes",
                        to="students.student",
                    ),
                ),
                (
                    "tutor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_notes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Progress Note",
                "verbose_name_plural": "Progress Notes",
            },
        ),
        migrations.CreateModel(
            name="PortalMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("sender_is_tutor", models.BooleanField(default=False)),
                ("text", models.TextField(verbose_name="Message")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_by_tutor", models.BooleanField(default=False)),
                ("read_by_portal", models.BooleanField(default=False)),
                (
                    "sender_portal_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sent_messages",
                        to="portal.portaluser",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_messages",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
                "verbose_name": "Portal Message",
                "verbose_name_plural": "Portal Messages",
            },
        ),
    ]

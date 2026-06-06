from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0002_parentstudentlink_invite_token_is_active"),
        ("students", "0008_student_is_adult"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("file", models.FileField(upload_to="student_documents/", verbose_name="Datei")),
                ("name", models.CharField(blank=True, max_length=200, verbose_name="Bezeichnung")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("uploaded_by_tutor", models.BooleanField(default=False)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="students.student",
                        verbose_name="Schüler",
                    ),
                ),
                (
                    "uploaded_by_portal_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_documents",
                        to="portal.portaluser",
                    ),
                ),
            ],
            options={
                "verbose_name": "Schülerdokument",
                "verbose_name_plural": "Schülerdokumente",
                "ordering": ["-uploaded_at"],
            },
        ),
    ]

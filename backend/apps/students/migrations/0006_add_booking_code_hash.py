# Add booking_code_hash for Public Booking authentication

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0005_student_user_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="booking_code_hash",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="SHA-256 hash of the public booking code (never store plaintext)",
                max_length=64,
                null=True,
            ),
        ),
    ]

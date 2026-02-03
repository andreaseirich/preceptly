# Generated for Premium Billing Pro

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_userprofile_public_booking_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="next_invoice_number",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Next sequential invoice number (Premium only).",
            ),
        ),
    ]

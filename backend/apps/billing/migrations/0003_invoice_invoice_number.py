# Generated for Premium Billing Pro

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0002_alter_invoice_options_alter_invoiceitem_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="invoice_number",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Sequential invoice number (Premium). INV-<id> fallback for Basic.",
                max_length=50,
                null=True,
            ),
        ),
    ]

# Allow negative invoice line amounts and totals (TutorSpace no-show deductions)

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0010_add_paid_at_sent_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="total_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Total invoice amount (may be negative if items include deductions).",
                max_digits=10,
            ),
        ),
        migrations.AlterField(
            model_name="invoiceitem",
            name="amount",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Amount for this item (negative for deductions, e.g. TutorSpace no-show).",
                max_digits=10,
            ),
        ),
    ]

# Migration 3: owner NOT NULL, indexes, UniqueConstraint

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_backfill_invoice_owner"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="owner",
            field=models.ForeignKey(
                help_text="Tutor who owns this invoice",
                on_delete=models.CASCADE,
                related_name="invoices",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(fields=["owner", "created_at"], name="billing_inv_owner_i_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                condition=models.Q(invoice_number__isnull=False),
                fields=("owner", "invoice_number"),
                name="uniq_owner_invoice_number_not_null",
            ),
        ),
    ]

# Migration 1: Add owner as nullable

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0003_invoice_invoice_number"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text="Tutor who owns this invoice",
                null=True,
                on_delete=models.CASCADE,
                related_name="invoices",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

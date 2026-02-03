# Update InvoiceItem.lesson FK to lessons.Session (same table as Lesson). State only.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0006_invoice_owner_not_null_constraints"),
        ("lessons", "0008_rename_lesson_to_session_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="invoiceitem",
                    name="lesson",
                    field=models.ForeignKey(
                        blank=True,
                        help_text="Associated lesson (may be deleted later)",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invoice_items",
                        to="lessons.session",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

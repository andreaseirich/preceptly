from django.db import migrations, models
from django.db.models import Q


def fix_invoice_periods(apps, schema_editor):
    Invoice = apps.get_model("billing", "Invoice")
    count = 0
    for inv in Invoice.objects.filter(period_end__lt=models.F("period_start")):
        inv.period_end = inv.period_start
        inv.save(update_fields=["period_end"])
        count += 1
    if count:
        print(f"  Fixed {count} invoices with period_end < period_start")


def fix_duplicate_invoice_items(apps, schema_editor):
    InvoiceItem = apps.get_model("billing", "InvoiceItem")
    from django.db.models import Count

    dupes = (
        InvoiceItem.objects.filter(lesson__isnull=False)
        .values("invoice", "lesson")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    for d in dupes:
        items = InvoiceItem.objects.filter(invoice_id=d["invoice"], lesson_id=d["lesson"]).order_by(
            "id"
        )
        keep = items.first()
        items.exclude(pk=keep.pk).delete()
        print(f"  Removed duplicate InvoiceItems for invoice={d['invoice']}, lesson={d['lesson']}")


def drop_invoice_period_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE billing_invoice DROP CONSTRAINT IF EXISTS invoice_period_end_gte_start"
        )


def drop_invoiceitem_unique_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        # UniqueConstraint with condition is created as an INDEX in PostgreSQL, not a table constraint
        cursor.execute("DROP INDEX IF EXISTS uniq_invoiceitem_invoice_lesson")
        cursor.execute(
            "ALTER TABLE billing_invoiceitem DROP CONSTRAINT IF EXISTS uniq_invoiceitem_invoice_lesson"
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0012_alter_invoiceitem_duration_minutes"),
    ]

    operations = [
        migrations.RunPython(fix_invoice_periods, noop),
        migrations.RunPython(fix_duplicate_invoice_items, noop),
        migrations.RunPython(drop_invoice_period_constraint, noop),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="invoice_period_end_gte_start",
            ),
        ),
        migrations.RunPython(drop_invoiceitem_unique_constraint, noop),
        migrations.AddConstraint(
            model_name="invoiceitem",
            constraint=models.UniqueConstraint(
                fields=["invoice", "lesson"],
                condition=Q(lesson__isnull=False),
                name="uniq_invoiceitem_invoice_lesson",
            ),
        ),
    ]

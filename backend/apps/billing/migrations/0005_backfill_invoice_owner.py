# Migration 2: Data migration to backfill owner

from django.db import migrations


def backfill_invoice_owner(apps, schema_editor):
    Invoice = apps.get_model("billing", "Invoice")
    InvoiceItem = apps.get_model("billing", "InvoiceItem")
    Contract = apps.get_model("contracts", "Contract")
    Student = apps.get_model("students", "Student")

    failed_ids = []
    for invoice in Invoice.objects.filter(owner__isnull=True).select_related(
        "contract__student__user"
    ):
        owner_id = None
        if invoice.contract_id:
            try:
                owner_id = invoice.contract.student.user_id
            except (Contract.DoesNotExist, Student.DoesNotExist, AttributeError):
                owner_id = None  # Relation missing; fall through to items resolution

        if owner_id is None:
            item = (
                InvoiceItem.objects.filter(invoice=invoice, lesson__isnull=False)
                .order_by("id")
                .first()
            )
            if item and item.lesson_id:
                Lesson = apps.get_model("lessons", "Lesson")
                lesson = (
                    Lesson.objects.filter(pk=item.lesson_id)
                    .select_related("contract__student__user")
                    .first()
                )
                if lesson and lesson.contract_id:
                    try:
                        owner_id = lesson.contract.student.user_id
                    except (Contract.DoesNotExist, Student.DoesNotExist, AttributeError):
                        owner_id = None  # Relation missing; cannot resolve owner

        if owner_id is None:
            failed_ids.append(invoice.id)
        else:
            invoice.owner_id = owner_id
            invoice.save(update_fields=["owner_id"])

    if failed_ids:
        raise ValueError(
            f"Cannot resolve owner for Invoice(s) with id: {failed_ids}. "
            "Each invoice must have a contract or at least one item with a lesson that has a contract."
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_invoice_owner"),
        ("contracts", "0004_alter_contract_options_and_more"),
        ("lessons", "0007_session_created_via"),
        ("students", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_invoice_owner, noop),
    ]

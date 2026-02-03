# Migration 2: Data migration to backfill owner

from django.db import migrations


def _owner_from_contract(invoice, Contract, Student):
    """Resolve owner from invoice.contract.student.user; return None on missing relation."""
    try:
        return invoice.contract.student.user_id if invoice.contract_id else None
    except (Contract.DoesNotExist, Student.DoesNotExist, AttributeError):
        return None


def _owner_from_first_item(apps, invoice, Contract, Student):
    """Resolve owner from first item's lesson.contract.student.user; return None on failure."""
    InvoiceItem = apps.get_model("billing", "InvoiceItem")
    Lesson = apps.get_model("lessons", "Lesson")
    item = (
        InvoiceItem.objects.filter(invoice=invoice, lesson__isnull=False)
        .order_by("id")
        .first()
    )
    if not item or not item.lesson_id:
        return None
    lesson = (
        Lesson.objects.filter(pk=item.lesson_id)
        .select_related("contract__student__user")
        .first()
    )
    if not lesson or not lesson.contract_id:
        return None
    try:
        return lesson.contract.student.user_id
    except (Contract.DoesNotExist, Student.DoesNotExist, AttributeError):
        return None


def backfill_invoice_owner(apps, schema_editor):
    Invoice = apps.get_model("billing", "Invoice")
    Contract = apps.get_model("contracts", "Contract")
    Student = apps.get_model("students", "Student")

    failed_ids = []
    for invoice in Invoice.objects.filter(owner__isnull=True).select_related(
        "contract__student__user"
    ):
        owner_id = _owner_from_contract(invoice, Contract, Student)
        if owner_id is None:
            owner_id = _owner_from_first_item(apps, invoice, Contract, Student)

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

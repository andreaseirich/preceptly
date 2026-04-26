"""
Management Command: Setzt alle bezahlten Lessons auf "unterrichtet" zurück.

Verwendung:
    python manage.py reset_paid_lessons
    python manage.py reset_paid_lessons --delete-invoices
"""

from django.core.management.base import BaseCommand

from apps.billing.models import InvoiceItem
from apps.lessons.models import Lesson


class Command(BaseCommand):
    help = "Setzt alle Lessons mit Status PAID auf TAUGHT zurück."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-invoices",
            action="store_true",
            help="Löscht auch die zugehörigen Rechnungen (und InvoiceItems)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Zeigt nur an, was geändert würde, ohne Änderungen vorzunehmen",
        )

    def handle(self, *args, **options):
        delete_invoices = options["delete_invoices"]
        dry_run = options["dry_run"]

        # Finde alle Lessons mit Status PAID
        paid_lessons = Lesson.objects.filter(status="paid")

        if not paid_lessons.exists():
            self.stdout.write(self.style.SUCCESS("Keine Lessons mit Status PAID gefunden."))
            return

        count = paid_lessons.count()
        self.stdout.write(f"Gefunden: {count} Lesson(s) mit Status PAID")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN: Es werden keine Änderungen vorgenommen.")
            )
            for lesson in paid_lessons[:10]:  # Zeige erste 10 als Beispiel
                invoice_items = InvoiceItem.objects.filter(lesson=lesson)
                self.stdout.write(
                    f"  - Lesson {lesson.id}: {lesson.date} {lesson.start_time} "
                    f"({invoice_items.count()} Rechnungsposten)"
                )
            if count > 10:
                self.stdout.write(f"  ... und {count - 10} weitere")
            return

        # Sammle betroffene Rechnungen (falls gelöscht werden sollen)
        affected_invoices = set()
        if delete_invoices:
            for lesson in paid_lessons:
                invoice_items = InvoiceItem.objects.filter(lesson=lesson)
                for item in invoice_items:
                    if item.invoice:
                        affected_invoices.add(item.invoice)

        # Setze Lessons auf TAUGHT zurück
        updated_count = paid_lessons.update(status="taught")

        if delete_invoices:
            # Lösche Rechnungen (CASCADE löscht automatisch InvoiceItems)
            invoice_count = len(affected_invoices)
            for invoice in affected_invoices:
                invoice.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"{updated_count} Lesson(s) auf TAUGHT zurückgesetzt. "
                    f"{invoice_count} Rechnung(en) gelöscht."
                )
            )
        else:
            # Prüfe, ob es InvoiceItems gibt, die jetzt "orphaned" sind
            orphaned_items = InvoiceItem.objects.filter(lesson__status="taught")
            orphaned_count = orphaned_items.count()

            if orphaned_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"{updated_count} Lesson(s) auf TAUGHT zurückgesetzt. "
                        f"Hinweis: {orphaned_count} Rechnungsposten verweisen noch auf diese Lessons. "
                        f"Verwenden Sie --delete-invoices, um auch die Rechnungen zu löschen."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"{updated_count} Lesson(s) auf TAUGHT zurückgesetzt.")
                )

"""
Management command: Sets payer to Abacus for invoices in October, November, December.

Usage:
    python manage.py set_abacus_payer_oct_nov_dec
    python manage.py set_abacus_payer_oct_nov_dec --year 2024
    python manage.py set_abacus_payer_oct_nov_dec --dry-run
"""

from datetime import date

from apps.billing.models import Invoice
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sets payer_name to 'Abacus' for invoices in October, November, December."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Year to process (default: current year)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making changes",
        )

    def handle(self, *args, **options):
        year = options["year"]
        if year is None:
            year = date.today().year
        dry_run = options["dry_run"]

        oct_start = date(year, 10, 1)
        dec_end = date(year, 12, 31)

        invoices = Invoice.objects.filter(
            period_start__lte=dec_end, period_end__gte=oct_start
        ).order_by("period_start")

        if not invoices.exists():
            self.stdout.write(self.style.WARNING(f"No invoices found for October–December {year}."))
            return

        count = invoices.count()
        self.stdout.write(f"Found {count} invoice(s) for Oct–Dec {year}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: No changes will be made."))

        updated = 0
        for inv in invoices:
            if inv.payer_name != "Abacus":
                if dry_run:
                    self.stdout.write(
                        f"  Would update #{inv.id}: "
                        f"'{inv.payer_name}' -> 'Abacus' "
                        f"({inv.period_start} - {inv.period_end})"
                    )
                else:
                    old_name = inv.payer_name
                    inv.payer_name = "Abacus"
                    inv.save(update_fields=["payer_name", "updated_at"])
                    self.stdout.write(
                        f"  Updated #{inv.id}: '{old_name}' -> 'Abacus' "
                        f"({inv.period_start} - {inv.period_end})"
                    )
                updated += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Would update {updated} invoice(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated {updated} invoice(s)."))

"""
Einmaliger Bereinigungsbefehl: loescht alle per Portal erstellten Termine.

Verwendung (Railway One-Off Command oder railway run):
    python manage.py clear_portal_bookings --dry-run   # nur anzeigen
    python manage.py clear_portal_bookings --confirm   # wirklich loeschen
"""

from django.core.management.base import BaseCommand

from apps.lessons.models import Session


class Command(BaseCommand):
    help = "Loescht alle per Portal-Buchung erstellten Termine (created_via=portal_booking)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nur anzeigen, nicht loeschen",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Wirklich loeschen (Pflichtflag)",
        )

    def handle(self, *args, **options):
        qs = Session.objects.filter(created_via="portal_booking").select_related("contract")
        count = qs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Keine Portal-Buchungen gefunden."))
            return

        self.stdout.write(f"Gefundene Portal-Buchungen: {count}")
        for s in qs.order_by("date", "start_time")[:50]:
            self.stdout.write(f"  {s.date}  {s.start_time}  {s.contract.full_name}  [{s.status}]")
        if count > 50:
            self.stdout.write(f"  ... und {count - 50} weitere")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN — nichts geloescht."))
            return

        if not options["confirm"]:
            self.stdout.write(
                self.style.ERROR(
                    "Bitte --confirm angeben um wirklich zu loeschen, oder --dry-run zum Vorschauen."
                )
            )
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"{deleted} Portal-Buchungen geloescht."))

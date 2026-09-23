"""Alte Zugriffsprotokolle löschen (läuft sonst automatisch einmal täglich)."""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.middleware import DEFAULT_REQUEST_LOG_RETENTION_DAYS, purge_old_request_logs


class Command(BaseCommand):
    help = "Löscht Zugriffsprotokolle, die älter sind als die Aufbewahrungsfrist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Aufbewahrungsfrist in Tagen (Standard: REQUEST_LOG_RETENTION_DAYS).",
        )

    def handle(self, *args, **options):
        days = options["days"] or getattr(
            settings, "REQUEST_LOG_RETENTION_DAYS", DEFAULT_REQUEST_LOG_RETENTION_DAYS
        )
        deleted = purge_old_request_logs(days)
        self.stdout.write(self.style.SUCCESS(f"{deleted} Einträge älter als {days} Tage gelöscht."))

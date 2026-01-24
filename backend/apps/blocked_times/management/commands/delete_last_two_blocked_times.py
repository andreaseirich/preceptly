"""
Management command to delete the two most recently created blocked times.

Usage:
    python manage.py delete_last_two_blocked_times [--dry-run]
"""

from apps.blocked_times.models import BlockedTime
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Deletes the two most recently created blocked times"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Finde die beiden neuesten Blockzeiten (nach created_at sortiert)
        # Hole zuerst die IDs, da delete() nicht mit Slicing funktioniert
        blocked_time_ids = list(BlockedTime.objects.order_by('-created_at').values_list('id', flat=True)[:2])
        
        if not blocked_time_ids:
            self.stdout.write(self.style.SUCCESS("No blocked times found."))
            return
        
        # Lade die Objekte für Anzeige
        blocked_times = BlockedTime.objects.filter(id__in=blocked_time_ids).order_by('-created_at')
        
        count = len(blocked_time_ids)
        self.stdout.write(f"\nFound {count} most recent blocked time(s):")
        
        for bt in blocked_times:
            self.stdout.write(
                f"  - ID {bt.pk}: {bt.title} - {bt.start_datetime.strftime('%Y-%m-%d %H:%M')} "
                f"(created: {bt.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
            )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: No blocked times were deleted."))
        else:
            # Lösche die Blockzeiten (ohne Slice)
            deleted_count, deleted_objects = BlockedTime.objects.filter(id__in=blocked_time_ids).delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully deleted {deleted_count} blocked time(s)."
                )
            )

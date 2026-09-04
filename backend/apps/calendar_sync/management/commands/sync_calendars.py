"""
Management command run periodically (via cron on the machine that also
has network access to any self-hosted CalDAV server involved, if any -
for the standard case of iCloud/Google CalDAV this can run from anywhere
including Railway itself) to sync all connected calendars.

    python manage.py sync_calendars
"""

import logging

from django.core.management.base import BaseCommand

from apps.calendar_sync.sync_service import sync_all_active_connections

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync all active CalendarConnections with their external CalDAV calendars."

    def handle(self, *args, **options):
        totals = sync_all_active_connections()
        self.stdout.write(
            self.style.SUCCESS(
                "Calendar sync done: pushed=%(pushed)s pulled=%(pulled)s imported=%(imported)s "
                "deleted=%(deleted)s conflicts=%(conflicts)s errors=%(errors)s" % totals
            )
        )

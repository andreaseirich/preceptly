"""
Management command: Remove orphaned invoice PDF files from storage.

Scans MEDIA_ROOT/invoices_pdf/ and deletes files not referenced by any Invoice.invoice_pdf.
Safe to run if MEDIA_ROOT is missing or empty.

Usage:
    python manage.py cleanup_orphan_invoice_pdfs
    python manage.py cleanup_orphan_invoice_pdfs --dry-run
"""

import os

from apps.billing.models import Invoice
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete invoice PDF files that are not referenced by any Invoice."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        media_root = getattr(settings, "MEDIA_ROOT", None)
        if not media_root:
            self.stdout.write(self.style.WARNING("MEDIA_ROOT not configured. Nothing to do."))
            return
        media_root = os.path.normpath(str(media_root))
        if not os.path.isdir(media_root):
            self.stdout.write(
                self.style.WARNING("MEDIA_ROOT does not exist or is not a directory.")
            )
            return

        invoices_pdf_dir = os.path.join(media_root, "invoices_pdf")
        if not os.path.isdir(invoices_pdf_dir):
            self.stdout.write("invoices_pdf directory does not exist. Nothing to clean.")
            return

        referenced = set(
            Invoice.objects.filter(invoice_pdf__isnull=False)
            .exclude(invoice_pdf="")
            .values_list("invoice_pdf", flat=True)
        )
        referenced = {os.path.normpath(p).replace(os.sep, "/") for p in referenced}

        orphans = []
        for root, _dirs, files in os.walk(invoices_pdf_dir, topdown=False):
            for name in files:
                full_path = os.path.join(root, name)
                try:
                    rel = os.path.relpath(full_path, media_root)
                except ValueError:
                    continue
                rel_normalized = rel.replace(os.sep, "/")
                if rel_normalized not in referenced:
                    orphans.append(full_path)

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No orphaned invoice PDFs found."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: Would delete:"))
            for p in sorted(orphans):
                self.stdout.write(f"  {p}")
            self.stdout.write(f"Total: {len(orphans)} file(s)")
            return

        deleted = 0
        for full_path in orphans:
            try:
                os.remove(full_path)
                deleted += 1
            except OSError:
                self.stdout.write(self.style.WARNING(f"Could not delete: {full_path}"))

        for root, dirs, _files in os.walk(invoices_pdf_dir, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                except OSError:
                    pass

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} orphaned PDF file(s)."))

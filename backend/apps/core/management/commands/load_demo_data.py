"""
Management command to load demo data idempotently.
Deletes all existing demo data and then generates new data using seed_demo_data.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load demo data idempotently (deletes existing data first, then seeds new data)"

    def handle(self, *args, **options):
        self.stdout.write("Loading demo data...")
        self.stdout.write(self.style.WARNING("This will delete all existing data and create fresh demo data."))

        # First, clear all demo data
        self.stdout.write("\n1. Clearing existing demo data...")
        try:
            call_command("clear_demo_data", confirm=True, verbosity=0)
            self.stdout.write(self.style.SUCCESS("✓ Existing data cleared"))
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Note: clear_demo_data had issues: {e}")
            )
            # Continue anyway - seed_demo_data will handle clearing if needed

        # Then, seed new demo data
        self.stdout.write("\n2. Generating fresh demo data...")
        try:
            call_command("seed_demo_data", clear=False, verbosity=1)
            self.stdout.write(self.style.SUCCESS("\n✓ Demo data generated successfully"))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error generating demo data: {e}")
            )
            raise

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write(self.style.SUCCESS("Demo data loaded successfully!"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write("\nDemo logins:")
        self.stdout.write("  - demo_premium / demo123 (premium)")
        self.stdout.write("  - demo_user / demo123 (standard)")
        self.stdout.write("\nNote: Use demo_premium to test AI lesson plan features.")

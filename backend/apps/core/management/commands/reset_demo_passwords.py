"""
Management command to reset demo user passwords to 'demo123'.

This ensures that demo_premium and demo_user can always be logged in
with the password 'demo123', regardless of how they were created.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reset passwords for demo users to 'demo123'"

    def handle(self, *args, **options):
        demo_users = ["demo_premium", "demo_user"]
        updated_count = 0

        for username in demo_users:
            try:
                user = User.objects.get(username=username)
                user.set_password("demo123")
                user.is_active = True
                user.is_staff = True
                user.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Reset password for '{username}' to 'demo123'")
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ User '{username}' does not exist. Run 'python manage.py load_demo_data' first."
                    )
                )

        if updated_count == 0:
            self.stdout.write(
                self.style.ERROR(
                    "No demo users found. Please run 'python manage.py load_demo_data' first."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully reset passwords for {updated_count} demo user(s)"
                )
            )

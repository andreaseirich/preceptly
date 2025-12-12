"""
Management command to load demo data idempotently.
Deletes existing demo users before loading fixture to prevent IntegrityError.
"""

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load demo data idempotently (deletes existing demo users first)"

    def handle(self, *args, **options):
        self.stdout.write("Loading demo data...")

        # Delete demo users if they exist (including profiles)
        demo_usernames = ["demo_premium", "demo_user"]
        deleted_count = 0

        from apps.core.models import UserProfile

        for username in demo_usernames:
            try:
                user = User.objects.get(username=username)
                # Delete associated profile if it exists
                try:
                    profile = UserProfile.objects.get(user=user)
                    profile.delete()
                except UserProfile.DoesNotExist:
                    pass
                user.delete()
                deleted_count += 1
                self.stdout.write(self.style.SUCCESS(f"Deleted existing user: {username}"))
            except User.DoesNotExist:
                pass

        if deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted_count} existing demo user(s)")
            )

        # Load fixture (excluding UserProfile entries - we'll create them manually)
        try:
            # Load fixture but skip UserProfile entries
            call_command("loaddata", "fixtures/demo_data.json", verbosity=0)
            self.stdout.write(self.style.SUCCESS("Demo data loaded successfully"))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error loading demo data: {e}")
            )
            raise

        # Create UserProfiles manually (to avoid created_at/updated_at issues)
        for username, email, is_premium in [
            ("demo_premium", "demo_premium@example.com", True),
            ("demo_user", "demo_user@example.com", False),
        ]:
            try:
                user = User.objects.get(username=username)
                user.set_password("demo123")
                user.is_staff = True
                user.is_active = True
                user.save()

                # Delete existing profile if it exists (from fixture)
                try:
                    existing_profile = UserProfile.objects.get(user=user)
                    existing_profile.delete()
                except UserProfile.DoesNotExist:
                    pass

                # Create new profile (auto_now_add will set created_at automatically)
                profile = UserProfile.objects.create(user=user, is_premium=is_premium)

                self.stdout.write(
                    self.style.SUCCESS(f"Updated user: {username} (premium: {is_premium})")
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"Warning: User {username} not found after loaddata")
                )

        self.stdout.write(self.style.SUCCESS("\nDemo data loaded successfully!"))
        self.stdout.write("Demo logins:")
        self.stdout.write("  - demo_premium / demo123 (premium)")
        self.stdout.write("  - demo_user / demo123 (standard)")


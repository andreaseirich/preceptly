"""
Management command to replace demo users with a personal user.

This command:
1. Finds all demo users (username contains 'demo')
2. Creates a new user for you
3. Transfers UserProfile settings (premium status, working hours) from demo_premium if it exists
4. Deletes demo users (which also deletes their UserProfiles)

Usage:
    python manage.py replace_demo_users --username your_username --email your_email [--password your_password] [--premium]
"""

from apps.core.models import UserProfile
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from getpass import getpass


class Command(BaseCommand):
    help = "Replace demo users with a personal user"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            required=True,
            help="Username for the new user",
        )
        parser.add_argument(
            "--email",
            type=str,
            required=True,
            help="Email for the new user",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Password for the new user (will prompt if not provided)",
        )
        parser.add_argument(
            "--premium",
            action="store_true",
            help="Make the new user a premium user",
        )
        parser.add_argument(
            "--first-name",
            type=str,
            default="",
            help="First name for the new user",
        )
        parser.add_argument(
            "--last-name",
            type=str,
            default="",
            help="Last name for the new user",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        username = options["username"]
        email = options["email"]
        password = options.get("password")
        is_premium = options.get("premium", False)
        first_name = options.get("first_name", "")
        last_name = options.get("last_name", "")

        # Find demo users
        demo_users = User.objects.filter(username__icontains="demo")

        if not demo_users.exists():
            self.stdout.write(self.style.WARNING("No demo users found."))
            return

        self.stdout.write(f"\nFound {demo_users.count()} demo user(s):")
        for user in demo_users:
            profile = getattr(user, "profile", None)
            premium_str = " (Premium)" if profile and profile.is_premium else ""
            self.stdout.write(f"  - {user.username} ({user.email}){premium_str}")

        # Check if new user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f"\nUser '{username}' already exists!"))
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.ERROR(f"\nEmail '{email}' is already in use!"))
            return

        # Get password if not provided
        if not password:
            password = getpass("Enter password for new user: ")
            password_confirm = getpass("Confirm password: ")
            if password != password_confirm:
                self.stdout.write(self.style.ERROR("Passwords do not match!"))
                return

        # Get settings from demo_premium if it exists
        demo_premium = demo_users.filter(username="demo_premium").first()
        demo_premium_profile = None
        if demo_premium:
            demo_premium_profile = getattr(demo_premium, "profile", None)
            if demo_premium_profile:
                # Use premium status from demo_premium if not explicitly set
                if not options.get("premium"):
                    is_premium = demo_premium_profile.is_premium
                self.stdout.write(
                    f"\nFound demo_premium with settings:"
                    f"\n  - Premium: {demo_premium_profile.is_premium}"
                    f"\n  - Premium since: {demo_premium_profile.premium_since}"
                    f"\n  - Default working hours: {bool(demo_premium_profile.default_working_hours)}"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: Would perform the following:"))
            self.stdout.write(f"  1. Create user: {username} ({email})")
            self.stdout.write(f"  2. Create UserProfile with premium={is_premium}")
            if demo_premium_profile and demo_premium_profile.default_working_hours:
                self.stdout.write(f"  3. Copy default_working_hours from demo_premium")
            self.stdout.write(f"  4. Delete {demo_users.count()} demo user(s)")
            return

        # Create new user
        self.stdout.write(f"\nCreating new user: {username}...")
        new_user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,  # Make staff so they can access admin
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS(f"✓ User '{username}' created"))

        # Create UserProfile
        self.stdout.write("Creating UserProfile...")
        profile_data = {
            "is_premium": is_premium,
        }

        # Copy premium_since if from demo_premium
        if demo_premium_profile and demo_premium_profile.is_premium and is_premium:
            if demo_premium_profile.premium_since:
                profile_data["premium_since"] = demo_premium_profile.premium_since
            else:
                profile_data["premium_since"] = timezone.now()

        # Copy default_working_hours from demo_premium if it exists
        if demo_premium_profile and demo_premium_profile.default_working_hours:
            profile_data["default_working_hours"] = demo_premium_profile.default_working_hours

        new_profile = UserProfile.objects.create(user=new_user, **profile_data)
        self.stdout.write(self.style.SUCCESS(f"✓ UserProfile created (Premium: {is_premium})"))

        if demo_premium_profile and demo_premium_profile.default_working_hours:
            self.stdout.write(
                self.style.SUCCESS("✓ Default working hours copied from demo_premium")
            )

        # Delete demo users
        self.stdout.write(f"\nDeleting {demo_users.count()} demo user(s)...")
        deleted_count = 0
        for user in demo_users:
            username_to_delete = user.username
            user.delete()  # This will also delete the UserProfile due to CASCADE
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted user: {username_to_delete}"))
            deleted_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'=' * 50}\n"
                f"Successfully replaced demo users!\n"
                f"{'=' * 50}\n"
                f"New user: {username} ({email})\n"
                f"Premium: {is_premium}\n"
                f"Demo users deleted: {deleted_count}\n"
            )
        )

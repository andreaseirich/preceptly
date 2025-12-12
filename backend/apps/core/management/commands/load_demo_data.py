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

        # Load fixture using a workaround for auto_now_add/auto_now fields
        # We'll use loaddata with --ignorenonexistent and then touch all objects
        try:
            # First, try to load the fixture
            # If it fails due to created_at/updated_at, we'll handle it differently
            call_command("loaddata", "fixtures/demo_data.json", verbosity=0, ignore=False)
            self.stdout.write(self.style.SUCCESS("Demo data loaded successfully"))
            
            # Touch all objects with auto_now_add/auto_now to ensure timestamps are set
            from apps.students.models import Student
            from apps.contracts.models import Contract, ContractMonthlyPlan
            from apps.lessons.models import Lesson
            from apps.lesson_plans.models import LessonPlan
            
            # Update all objects to trigger auto_now/auto_now_add
            for student in Student.objects.all():
                student.save(update_fields=['updated_at'])
            
            for contract in Contract.objects.all():
                contract.save(update_fields=['updated_at'])
            
            for plan in ContractMonthlyPlan.objects.all():
                plan.save(update_fields=['updated_at'])
            
            for lesson in Lesson.objects.all():
                lesson.save(update_fields=['updated_at'])
            
            for plan in LessonPlan.objects.all():
                plan.save(update_fields=['updated_at'])
                
        except Exception as e:
            # If loaddata fails, try alternative approach: load without timestamps
            self.stdout.write(
                self.style.WARNING(f"Standard loaddata failed: {e}")
            )
            self.stdout.write("Trying alternative loading method...")
            
            # Use loaddata with --ignorenonexistent to skip problematic fields
            # Then manually create objects
            import json
            from django.utils import timezone
            from apps.students.models import Student
            from apps.contracts.models import Contract, ContractMonthlyPlan
            from apps.lessons.models import Lesson
            from apps.lesson_plans.models import LessonPlan
            
            with open("fixtures/demo_data.json", "r") as f:
                data = json.load(f)
            
            # Create objects manually, skipping auto fields
            for item in data:
                model_name = item["model"]
                fields = item["fields"]
                
                if model_name == "students.student":
                    Student.objects.get_or_create(
                        pk=item["pk"],
                        defaults={
                            **{k: v for k, v in fields.items() if k not in ["created_at", "updated_at"]}
                        }
                    )
                elif model_name == "contracts.contract":
                    Contract.objects.get_or_create(
                        pk=item["pk"],
                        defaults={
                            **{k: v for k, v in fields.items() if k not in ["created_at", "updated_at"]}
                        }
                    )
                elif model_name == "contracts.contractmonthlyplan":
                    ContractMonthlyPlan.objects.get_or_create(
                        pk=item["pk"],
                        defaults={
                            **{k: v for k, v in fields.items() if k not in ["created_at", "updated_at"]}
                        }
                    )
                elif model_name == "lessons.lesson":
                    Lesson.objects.get_or_create(
                        pk=item["pk"],
                        defaults={
                            **{k: v for k, v in fields.items() if k not in ["created_at", "updated_at"]}
                        }
                    )
                elif model_name == "lesson_plans.lessonplan":
                    LessonPlan.objects.get_or_create(
                        pk=item["pk"],
                        defaults={
                            **{k: v for k, v in fields.items() if k not in ["created_at", "updated_at"]}
                        }
                    )
                elif model_name == "auth.user":
                    # User is already handled above
                    pass
            
            self.stdout.write(self.style.SUCCESS("Demo data loaded using alternative method"))

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


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
            # Process in order: Users first, then Students, Contracts, Lessons, LessonPlans
            for item in data:
                model_name = item["model"]
                fields = item["fields"]
                pk = item["pk"]
                
                if model_name == "auth.user":
                    # User is already handled above or will be created by fixture
                    continue
                elif model_name == "students.student":
                    # Get or create student
                    student, created = Student.objects.get_or_create(
                        id=pk,
                        defaults={
                            "first_name": fields["first_name"],
                            "last_name": fields["last_name"],
                            "email": fields.get("email", ""),
                            "phone": fields.get("phone", ""),
                            "school": fields.get("school", ""),
                            "grade": fields.get("grade", ""),
                            "subjects": fields.get("subjects", ""),
                            "notes": fields.get("notes", ""),
                        }
                    )
                    if not created:
                        # Update existing (skip auto fields)
                        for key, value in fields.items():
                            if key not in ["created_at", "updated_at"]:
                                setattr(student, key, value)
                        student.save()
                    # Touch to ensure timestamps are set
                    student.save(update_fields=['updated_at'])
                elif model_name == "contracts.contract":
                    contract, created = Contract.objects.get_or_create(
                        id=pk,
                        defaults={
                            "student_id": fields["student"],
                            "institute": fields.get("institute", ""),
                            "hourly_rate": fields["hourly_rate"],
                            "unit_duration_minutes": fields["unit_duration_minutes"],
                            "start_date": fields.get("start_date"),
                            "end_date": fields.get("end_date"),
                            "is_active": fields.get("is_active", True),
                            "notes": fields.get("notes", ""),
                        }
                    )
                    if not created:
                        # Update existing - handle ForeignKeys correctly
                        for key, value in fields.items():
                            if key not in ["created_at", "updated_at"]:
                                # ForeignKeys need _id suffix
                                if key == "student":
                                    contract.student_id = value
                                else:
                                    setattr(contract, key, value)
                        contract.save()
                    # Touch to ensure timestamps are set
                    contract.save(update_fields=['updated_at'])
                elif model_name == "lessons.lesson":
                    lesson, created = Lesson.objects.get_or_create(
                        id=pk,
                        defaults={
                            "contract_id": fields["contract"],
                            "date": fields["date"],
                            "start_time": fields["start_time"],
                            "duration_minutes": fields["duration_minutes"],
                            "status": fields.get("status", "planned"),
                            "travel_time_before_minutes": fields.get("travel_time_before_minutes", 0),
                            "travel_time_after_minutes": fields.get("travel_time_after_minutes", 0),
                            "notes": fields.get("notes", ""),
                        }
                    )
                    if not created:
                        # Update existing - handle ForeignKeys correctly
                        for key, value in fields.items():
                            if key not in ["created_at", "updated_at"]:
                                # ForeignKeys need _id suffix
                                if key == "contract":
                                    lesson.contract_id = value
                                else:
                                    setattr(lesson, key, value)
                        lesson.save()
                    # Touch to ensure timestamps are set
                    lesson.save(update_fields=['updated_at'])
                elif model_name == "lesson_plans.lessonplan":
                    plan, created = LessonPlan.objects.get_or_create(
                        id=pk,
                        defaults={
                            "student_id": fields["student"],
                            "lesson_id": fields.get("lesson"),
                            "topic": fields["topic"],
                            "subject": fields["subject"],
                            "content": fields["content"],
                            "grade_level": fields.get("grade_level", ""),
                            "duration_minutes": fields.get("duration_minutes"),
                            "llm_model": fields.get("llm_model", ""),
                        }
                    )
                    if not created:
                        # Update existing - handle ForeignKeys correctly
                        for key, value in fields.items():
                            if key not in ["created_at", "updated_at"]:
                                # ForeignKeys need _id suffix
                                if key == "student":
                                    plan.student_id = value
                                elif key == "lesson":
                                    plan.lesson_id = value
                                else:
                                    setattr(plan, key, value)
                        plan.save()
                    # Touch to ensure timestamps are set
                    plan.save(update_fields=['updated_at'])
            
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


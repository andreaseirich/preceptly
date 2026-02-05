"""
Management command for creating demo data for TutorFlow.

Usage:
    python manage.py seed_demo_data           # Add demo data (idempotent for users)
    python manage.py seed_demo_data --clear   # Delete demo_premium/demo_user data only, then seed

Only demo_premium and demo_user are created or modified. Other users' data is never touched.

Creates:
    - 4 students with different profiles
    - Associated contracts (including ContractMonthlyPlan for quota conflicts)
    - Multiple lessons (including conflicts and recurring lessons)
    - Blocked times (including multi-day vacation and conflicts)
    - Premium user with generated lesson plan
    - Non-premium user for comparison
"""

from datetime import date, time, timedelta
from decimal import Decimal

from apps.billing.models import Invoice
from apps.billing.services import InvoiceService
from apps.blocked_times.models import BlockedTime
from apps.blocked_times.recurring_models import RecurringBlockedTime
from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.core.models import UserProfile
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_service import RecurringLessonService
from apps.students.models import Student
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Creates demo data for TutorFlow"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete demo user data only before seeding",
        )

    def _clear_demo_user_data(self):
        """Delete only data belonging to demo_premium and demo_user."""
        demo_users = User.objects.filter(username__in=["demo_premium", "demo_user"])
        if not demo_users.exists():
            return

        demo_user_ids = list(demo_users.values_list("id", flat=True))
        student_ids = list(
            Student.objects.filter(user_id__in=demo_user_ids).values_list("id", flat=True)
        )
        contract_ids = list(
            Contract.objects.filter(student_id__in=student_ids).values_list("id", flat=True)
        )

        LessonPlan.objects.filter(student_id__in=student_ids).delete()
        Invoice.objects.filter(owner_id__in=demo_user_ids).delete()
        Lesson.objects.filter(contract_id__in=contract_ids).delete()
        RecurringLesson.objects.filter(contract_id__in=contract_ids).delete()
        BlockedTime.objects.filter(user_id__in=demo_user_ids).delete()
        RecurringBlockedTime.objects.filter(user_id__in=demo_user_ids).delete()
        ContractMonthlyPlan.objects.filter(contract_id__in=contract_ids).delete()
        Contract.objects.filter(student_id__in=student_ids).delete()
        Student.objects.filter(user_id__in=demo_user_ids).delete()
        UserProfile.objects.filter(user_id__in=demo_user_ids).delete()
        User.objects.filter(id__in=demo_user_ids).delete()

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write(self.style.WARNING("Deleting demo user data only..."))
            self._clear_demo_user_data()

        self.stdout.write(self.style.SUCCESS("Creating demo data..."))

        # Create users first (required for multi-tenancy)
        premium_user, _ = User.objects.get_or_create(
            username="demo_premium",
            defaults={"email": "premium@example.com", "is_staff": True, "is_active": True},
        )
        premium_user.set_password("demo123")
        premium_user.is_staff = True
        premium_user.is_active = True
        premium_user.save()

        UserProfile.objects.get_or_create(
            user=premium_user,
            defaults={"is_premium": True, "premium_since": timezone.now()},
        )

        non_premium_user, _ = User.objects.get_or_create(
            username="demo_user",
            defaults={"email": "demo_user@example.com", "is_staff": True, "is_active": True},
        )
        non_premium_user.set_password("demo123")
        non_premium_user.is_staff = True
        non_premium_user.is_active = True
        non_premium_user.save()

        UserProfile.objects.get_or_create(user=non_premium_user, defaults={"is_premium": False})

        # Students (assigned to premium_user)
        student1 = Student.objects.create(
            user=premium_user,
            first_name="Max",
            last_name="Mustermann",
            email="max.mustermann@example.com",
            phone="0123-456789",
            school="Gymnasium XY",
            grade="Grade 10",
            subjects="Math, Physics",
            notes="Very motivated, needs support with algebra",
        )

        student2 = Student.objects.create(
            user=premium_user,
            first_name="Anna",
            last_name="Schmidt",
            email="anna.schmidt@example.com",
            phone="0123-456790",
            school="Realschule ABC",
            grade="Grade 9",
            subjects="German, English",
            notes="Good student, wants to prepare for final exams",
        )

        student3 = Student.objects.create(
            user=premium_user,
            first_name="Tom",
            last_name="Weber",
            email="tom.weber@example.com",
            school="Gymnasium XY",
            grade="Grade 11",
            subjects="Math, Chemistry",
        )

        student4 = Student.objects.create(
            user=premium_user,
            first_name="Lisa",
            last_name="Müller",
            email="lisa.mueller@example.com",
            school="Gymnasium XY",
            grade="Grade 8",
            subjects="German, English",
            notes="Recurring lessons every Monday and Wednesday",
        )

        # Contracts
        # Contract 1: With monthly quotas (for quota conflicts)
        contract1 = Contract.objects.create(
            student=student1,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 11, 1),
            is_active=True,
            notes="Weekly 2x Math - with monthly quotas",
        )

        # ContractMonthlyPlan for quota conflicts
        ContractMonthlyPlan.objects.create(contract=contract1, year=2025, month=11, planned_units=3)
        ContractMonthlyPlan.objects.create(contract=contract1, year=2025, month=12, planned_units=5)

        # Contract 2: With recurring lessons
        contract2 = Contract.objects.create(
            student=student2,
            institute="Tutoring Institute ABC",
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=90,
            start_date=date(2025, 10, 15),
            is_active=True,
            notes="Recurring lessons weekly",
        )

        # Contract 3: Single lessons only
        contract3 = Contract.objects.create(
            student=student3,
            hourly_rate=Decimal("28.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 12, 1),
            is_active=True,
            notes="Single lessons only",
        )

        # Contract 4: With recurring lessons (Mon+Wed)
        contract4 = Contract.objects.create(
            student=student4,
            hourly_rate=Decimal("22.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 11, 1),
            is_active=True,
            notes="Recurring lessons Monday and Wednesday",
        )

        # Lessons (with conflicts)
        today = timezone.now().date()

        lesson1 = Lesson.objects.create(
            contract=contract1,
            date=today + timedelta(days=1),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
            travel_time_before_minutes=15,
            travel_time_after_minutes=20,
            notes="Algebra: Linear Equations",
        )

        # Conflict: Overlap with lesson1
        Lesson.objects.create(
            contract=contract2,
            date=today + timedelta(days=1),
            start_time=time(14, 30),  # Overlap!
            duration_minutes=90,
            status="planned",
            travel_time_before_minutes=20,
            notes="German: Text Analysis",
        )

        Lesson.objects.create(
            contract=contract1,
            date=today + timedelta(days=3),
            start_time=time(16, 0),
            duration_minutes=60,
            status="planned",
            notes="Physics: Mechanics",
        )

        # Lesson4: Created as "taught" and then included in an invoice (automatically becomes "paid")
        lesson4 = Lesson.objects.create(
            contract=contract3,
            date=today - timedelta(days=2),
            start_time=time(15, 0),
            duration_minutes=60,
            status="taught",  # First create as "taught"
            notes="Math: Analysis",
        )

        # Quota conflict: Try to create more lessons than planned
        # November: 3 planned, but create 4 lessons (4th should have conflict)
        Lesson.objects.create(
            contract=contract1,
            date=date(2025, 11, 5),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
            notes="Math: Algebra - 1st lesson in November",
        )
        Lesson.objects.create(
            contract=contract1,
            date=date(2025, 11, 12),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
            notes="Math: Algebra - 2nd lesson in November",
        )
        Lesson.objects.create(
            contract=contract1,
            date=date(2025, 11, 19),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
            notes="Math: Algebra - 3rd lesson in November",
        )
        # This lesson should have a quota conflict (4th lesson, but only 3 planned)
        Lesson.objects.create(
            contract=contract1,
            date=date(2025, 11, 26),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
            notes="Math: Algebra - 4th lesson in November (QUOTA CONFLICT)",
        )

        # Recurring Lessons
        # Recurring Lesson 1: Weekly, Monday and Wednesday
        recurring1_start = today + timedelta(days=(7 - today.weekday()) % 7)  # Next Monday
        if recurring1_start <= today:
            recurring1_start += timedelta(days=7)

        recurring1 = RecurringLesson.objects.create(
            contract=contract4,
            start_date=recurring1_start,
            end_date=recurring1_start + timedelta(days=30),  # 4 weeks
            start_time=time(16, 0),
            duration_minutes=60,
            travel_time_before_minutes=15,
            travel_time_after_minutes=15,
            recurrence_type="weekly",
            notes="German: Grammar and Spelling",
            monday=True,
            tuesday=False,
            wednesday=True,
            thursday=False,
            friday=False,
            saturday=False,
            sunday=False,
            is_active=True,
        )

        # Generate lessons from recurring lesson
        RecurringLessonService.generate_lessons(recurring1, check_conflicts=True, dry_run=False)

        # Recurring Lesson 2: Weekly, Tuesday and Thursday
        recurring2_start = today + timedelta(days=(1 - today.weekday()) % 7)  # Next Tuesday
        if recurring2_start <= today:
            recurring2_start += timedelta(days=7)

        recurring2 = RecurringLesson.objects.create(
            contract=contract2,
            start_date=recurring2_start,
            end_date=recurring2_start + timedelta(days=21),  # 3 weeks
            start_time=time(15, 0),
            duration_minutes=90,
            travel_time_before_minutes=20,
            travel_time_after_minutes=20,
            recurrence_type="weekly",
            notes="English: Conversation and Grammar",
            monday=False,
            tuesday=True,
            wednesday=False,
            thursday=True,
            friday=False,
            saturday=False,
            sunday=False,
            is_active=True,
        )

        # Generate lessons from recurring lesson
        RecurringLessonService.generate_lessons(recurring2, check_conflicts=True, dry_run=False)

        # Blocked times (assigned to premium_user)
        BlockedTime.objects.create(
            user=premium_user,
            title="University Lecture",
            description="Mathematics lecture",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(today + timedelta(days=2), time(10, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(today + timedelta(days=2), time(12, 0))
            ),
            is_recurring=False,
        )

        # Blocked time 2: Multi-day vacation (3 days)
        vacation_start = today + timedelta(days=10)
        BlockedTime.objects.create(
            user=premium_user,
            title="Vacation",
            description="Multi-day vacation",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(vacation_start, time(0, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(vacation_start + timedelta(days=2), time(23, 59))
            ),
            is_recurring=False,
        )

        # Blocked time 3: Conflict with a lesson (intentional)
        conflict_date = today + timedelta(days=5)
        BlockedTime.objects.create(
            user=premium_user,
            title="Other Activity",
            description="Intentional conflict with a lesson",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(conflict_date, time(14, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(conflict_date, time(15, 30))
            ),
            is_recurring=False,
        )

        # Create a lesson that conflicts with blocked_time3
        Lesson.objects.create(
            contract=contract3,
            date=conflict_date,
            start_time=time(14, 30),  # Overlap with blocked_time3
            duration_minutes=60,
            status="planned",
            notes="Math: Analysis - CONFLICT WITH BLOCKED TIME",
        )

        # Demo LessonPlan 1 (for lesson1 - already existing)
        LessonPlan.objects.create(
            student=student1,
            lesson=lesson1,
            topic="Linear Equations",
            subject="Math",
            content="""# Lesson Plan: Linear Equations

## Introduction (10 Min)
- Review: What are linear equations?
- Example: 2x + 3 = 7

## Main Part (40 Min)
- Solving simple linear equations
- Practice exercises from the book
- Joint discussion

## Conclusion (10 Min)
- Summary of the most important steps
- Homework: 3 more exercises""",
            grade_level="Grade 10",
            duration_minutes=60,
            llm_model="gpt-3.5-turbo",
        )

        # Demo LessonPlan 2 (for lesson3 - no plan yet, can be generated with AI)
        # lesson3 has no plan yet, so premium user can test the AI function

        # Demo LessonPlan 3 (for one of the recurring lessons, if available)
        recurring_lessons = Lesson.objects.filter(contract=contract4).order_by("date")
        if recurring_lessons.exists():
            first_recurring_lesson = recurring_lessons.first()
            LessonPlan.objects.create(
                student=student4,
                lesson=first_recurring_lesson,
                topic="German Grammar: Sentence Components",
                subject="German",
                content="""# Lesson Plan: Sentence Components

## Introduction (10 Min)
- Review: What are sentence components?
- Examples: Subject, predicate, object

## Main Part (40 Min)
- Identifying sentence components in example sentences
- Practice exercises
- Joint discussion

## Conclusion (10 Min)
- Summary
- Homework: Analyze 5 sentences""",
                grade_level="Grade 8",
                duration_minutes=60,
                llm_model="gpt-3.5-turbo",
            )

        # --- Demo data for non_premium_user (demo_user) ---
        # Standard user gets a smaller set of data for comparison
        std_student1 = Student.objects.create(
            user=non_premium_user,
            first_name="Emma",
            last_name="Braun",
            email="emma.braun@example.com",
            phone="0987-654321",
            school="Gymnasium Z",
            grade="Grade 9",
            subjects="Math, English",
            notes="Standard demo student",
        )

        std_student2 = Student.objects.create(
            user=non_premium_user,
            first_name="Leon",
            last_name="Fischer",
            email="leon.fischer@example.com",
            school="Realschule M",
            grade="Grade 8",
            subjects="German",
        )

        std_contract1 = Contract.objects.create(
            student=std_student1,
            hourly_rate=Decimal("24.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 11, 1),
            is_active=True,
            notes="Weekly Math lessons",
        )

        std_contract2 = Contract.objects.create(
            student=std_student2,
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 10, 20),
            is_active=True,
            notes="German support",
        )

        ContractMonthlyPlan.objects.create(
            contract=std_contract1, year=2025, month=11, planned_units=4
        )

        Lesson.objects.create(
            contract=std_contract1,
            date=today + timedelta(days=2),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
            notes="Math: Fractions",
        )

        Lesson.objects.create(
            contract=std_contract1,
            date=today + timedelta(days=4),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
            notes="Math: Percentages",
        )

        Lesson.objects.create(
            contract=std_contract2,
            date=today + timedelta(days=3),
            start_time=time(16, 0),
            duration_minutes=60,
            status="planned",
            notes="German: Reading comprehension",
        )

        std_lesson_taught = Lesson.objects.create(
            contract=std_contract1,
            date=today - timedelta(days=5),
            start_time=time(11, 0),
            duration_minutes=60,
            status="taught",
            notes="Math: Basics - completed",
        )

        BlockedTime.objects.create(
            user=non_premium_user,
            title="Doctor Appointment",
            description="Annual checkup",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(today + timedelta(days=7), time(9, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(today + timedelta(days=7), time(10, 30))
            ),
            is_recurring=False,
        )

        if std_lesson_taught and std_lesson_taught.status == "taught":
            std_invoice = InvoiceService.create_invoice_from_lessons(
                period_start=std_lesson_taught.date,
                period_end=std_lesson_taught.date,
                contract=std_contract1,
                user=non_premium_user,
            )
            std_invoice.status = "draft"
            std_invoice.save(update_fields=["status", "updated_at"])

        # Create a demo invoice for lesson4 (so it becomes "paid")
        # Only if lesson4 exists and is marked as "taught"
        if lesson4 and lesson4.status == "taught":
            invoice_period_start = lesson4.date
            invoice_period_end = lesson4.date

            # Create invoice with lesson4
            demo_invoice = InvoiceService.create_invoice_from_lessons(
                period_start=invoice_period_start,
                period_end=invoice_period_end,
                contract=contract3,
                user=premium_user,
            )

            # Set invoice status to "sent" (as example)
            demo_invoice.status = "sent"
            demo_invoice.save(update_fields=["status", "updated_at"])

            # lesson4 should now be automatically set to "paid"

        self.stdout.write(self.style.SUCCESS("\n✅ Demo data successfully created:"))
        self.stdout.write(f"  - {Student.objects.count()} students")
        self.stdout.write(f"  - {Contract.objects.count()} contracts")
        self.stdout.write(f"  - {ContractMonthlyPlan.objects.count()} monthly plans")
        self.stdout.write(f"  - {Lesson.objects.count()} lessons")
        self.stdout.write(f"  - {RecurringLesson.objects.count()} recurring lessons")
        self.stdout.write(f"  - {BlockedTime.objects.count()} blocked times")
        self.stdout.write(
            f"  - {UserProfile.objects.filter(is_premium=True).count()} premium users"
        )
        self.stdout.write(
            f"  - {UserProfile.objects.filter(is_premium=False).count()} non-premium users"
        )
        self.stdout.write(f"  - {LessonPlan.objects.count()} lesson plans")
        self.stdout.write(f"  - {Invoice.objects.count()} invoices")
        self.stdout.write(self.style.SUCCESS("\n📝 Demo Logins:"))
        self.stdout.write("  Premium User:")
        self.stdout.write("    Username: demo_premium")
        self.stdout.write("    Password: demo123")
        self.stdout.write("  Standard User:")
        self.stdout.write("    Username: demo_user")
        self.stdout.write("    Password: demo123")
        self.stdout.write(self.style.WARNING("\n⚠️  Notes:"))
        self.stdout.write("  - Lesson1 and Lesson2 have a time conflict!")
        self.stdout.write("  - Lesson8 has a quota conflict (4th lesson, but only 3 planned)!")
        self.stdout.write("  - lesson_conflict has a conflict with blocked_time3!")
        self.stdout.write(
            "  - Recurring lessons were generated (Mon+Wed for student4, Tue+Thu for student2)!"
        )
        self.stdout.write("  - lesson3 has no lesson plan yet (can be generated with AI)!")

"""
Management command to clear demo data (students, lessons, contracts, invoices)
while keeping admin users and system settings.
"""

from apps.billing.models import Invoice, InvoiceItem
from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Clears all demo data (students, lessons, contracts, invoices) while keeping admin users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stdout.write(
                self.style.WARNING(
                    "This will delete all students, lessons, contracts, invoices, and related data.\n"
                    "Admin users will be kept.\n"
                    "Use --confirm to proceed."
                )
            )
            return

        self.stdout.write("Clearing demo data...")

        # Delete in correct order (respecting foreign key constraints)

        # 1. Delete InvoiceItems first (they reference Lessons)
        invoice_items_count = InvoiceItem.objects.count()
        InvoiceItem.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {invoice_items_count} invoice items"))

        # 2. Delete Invoices
        invoices_count = Invoice.objects.count()
        Invoice.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {invoices_count} invoices"))

        # 3. Delete LessonPlans (they reference Lessons and Students)
        lesson_plans_count = LessonPlan.objects.count()
        LessonPlan.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {lesson_plans_count} lesson plans"))

        # 4. Delete Lessons (they reference Contracts)
        lessons_count = Lesson.objects.count()
        Lesson.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {lessons_count} lessons"))

        # 5. Delete BlockedTimes
        blocked_times_count = BlockedTime.objects.count()
        BlockedTime.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {blocked_times_count} blocked times"))

        # 6. Delete ContractMonthlyPlans (they reference Contracts)
        monthly_plans_count = ContractMonthlyPlan.objects.count()
        ContractMonthlyPlan.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {monthly_plans_count} contract monthly plans")
        )

        # 9. Delete Contracts (they reference Students)
        contracts_count = Contract.objects.count()
        Contract.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {contracts_count} contracts"))

        # 10. Delete Students
        students_count = Student.objects.count()
        Student.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {students_count} students"))

        # Keep admin users - don't delete them
        admin_users = User.objects.filter(is_staff=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"\nKept {admin_users.count()} admin user(s): {', '.join(u.username for u in admin_users)}"
            )
        )

        self.stdout.write(self.style.SUCCESS("\nDemo data cleared successfully!"))

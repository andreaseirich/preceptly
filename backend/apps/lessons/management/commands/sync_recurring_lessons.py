"""
Management command to synchronize lessons with their recurring lesson series.

Usage:
    python manage.py sync_recurring_lessons [--student "First Last"]
    
This command finds all recurring lessons and synchronizes their generated lessons
with the current recurring lesson settings. This is useful to fix lessons that
were not properly updated when the series was modified.
"""

from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_utils import get_all_lessons_for_recurring
from apps.lessons.status_service import LessonStatusService
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Synchronizes lessons with their recurring lesson series"

    def add_arguments(self, parser):
        parser.add_argument(
            "--student",
            type=str,
            help="Student name (first last) to sync lessons for",
            nargs="?",
        )

    def handle(self, *args, **options):
        student_name = options.get("student")
        
        if student_name:
            # Parse student name
            parts = student_name.split(" ", 1)
            if len(parts) != 2:
                self.stdout.write(self.style.ERROR(f"Invalid student name format: {student_name}. Use 'First Last'"))
                return
            
            first_name, last_name = parts
            from apps.students.models import Student
            students = Student.objects.filter(first_name=first_name, last_name=last_name)
            
            if not students.exists():
                self.stdout.write(self.style.ERROR(f"Student '{student_name}' not found"))
                return
            
            student = students.first()
            self.stdout.write(f"Synchronizing lessons for student: {student}")
            
            # Find all contracts for this student
            contracts = student.contracts.all()
            recurring_lessons = RecurringLesson.objects.filter(contract__in=contracts, is_active=True)
        else:
            # Sync all recurring lessons
            recurring_lessons = RecurringLesson.objects.filter(is_active=True)

        total_updated = 0
        
        for recurring in recurring_lessons:
            # Find all lessons for this recurring lesson
            lessons = get_all_lessons_for_recurring(recurring)
            
            updated_count = 0
            for lesson in lessons:
                # Check if lesson needs updating
                needs_update = (
                    lesson.start_time != recurring.start_time
                    or lesson.duration_minutes != recurring.duration_minutes
                    or lesson.travel_time_before_minutes != recurring.travel_time_before_minutes
                    or lesson.travel_time_after_minutes != recurring.travel_time_after_minutes
                    or lesson.notes != recurring.notes
                )
                
                if needs_update:
                    # Update lesson with recurring lesson values
                    lesson.start_time = recurring.start_time
                    lesson.duration_minutes = recurring.duration_minutes
                    lesson.travel_time_before_minutes = recurring.travel_time_before_minutes
                    lesson.travel_time_after_minutes = recurring.travel_time_after_minutes
                    lesson.notes = recurring.notes
                    
                    # Update status
                    LessonStatusService.update_status_for_lesson(lesson)
                    lesson.save()
                    updated_count += 1
            
            if updated_count > 0:
                self.stdout.write(
                    f"Updated {updated_count} lesson(s) for series: {recurring.contract.student} - {recurring.get_active_weekdays_display()} {recurring.start_time}"
                )
                total_updated += updated_count

        if total_updated > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully synchronized {total_updated} lesson(s) with their recurring series."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("All lessons are already synchronized."))

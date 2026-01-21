"""
Management command to delete lessons for Anita on Tuesdays from 17.02.2026 onwards.

Usage:
    python manage.py delete_lessons_for_anita_tuesdays [--dry-run]
"""

from datetime import date

from apps.lessons.models import Lesson
from apps.students.models import Student
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Deletes lessons for Anita on Tuesdays from 17.02.2026 onwards"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Finde Anita
        anita = Student.objects.filter(first_name__icontains='Anita').first()
        
        if not anita:
            self.stdout.write(self.style.ERROR("Student 'Anita' nicht gefunden."))
            return
        
        self.stdout.write(f"Gefundener Student: {anita.full_name} (ID: {anita.pk})")
        
        # Finde alle Lessons für Anita ab 17.02.2026
        start_date = date(2026, 2, 17)
        lessons = Lesson.objects.filter(
            contract__student=anita,
            date__gte=start_date
        )
        
        # Filtere nach Dienstagen (weekday() == 1)
        tuesday_lessons = [l for l in lessons if l.date.weekday() == 1]
        
        if not tuesday_lessons:
            self.stdout.write(self.style.SUCCESS("Keine Lessons gefunden, die den Kriterien entsprechen."))
            return
        
        self.stdout.write(f"\nGefunden: {len(tuesday_lessons)} Lesson(s) an Dienstagen ab {start_date}:")
        for lesson in tuesday_lessons:
            self.stdout.write(f"  - {lesson.date} {lesson.start_time} (ID: {lesson.pk})")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: Keine Lessons wurden gelöscht."))
        else:
            # Lösche die Lessons
            lesson_ids = [l.pk for l in tuesday_lessons]
            deleted_count, _ = Lesson.objects.filter(pk__in=lesson_ids).delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nErfolgreich {deleted_count} Lesson(s) gelöscht."
                )
            )

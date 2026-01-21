"""
Management command to delete all lessons for Anita.

Usage:
    python manage.py delete_all_lessons_for_anita [--dry-run]
"""

from apps.lessons.models import Lesson
from apps.students.models import Student
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Deletes all lessons for Anita"

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
        
        # Finde alle Lessons für Anita
        lessons = Lesson.objects.filter(contract__student=anita)
        
        if not lessons.exists():
            self.stdout.write(self.style.SUCCESS("Keine Lessons gefunden."))
            return
        
        count = lessons.count()
        self.stdout.write(f"\nGefunden: {count} Lesson(s) für {anita.full_name}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: Keine Lessons wurden gelöscht."))
        else:
            # Lösche die Lessons
            deleted_count, _ = lessons.delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nErfolgreich {deleted_count} Lesson(s) gelöscht."
                )
            )

"""
Management command to delete all future lessons for Chris.

Usage:
    python manage.py delete_future_lessons_for_chris [--dry-run]
"""

from datetime import date
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Deletes all future lessons for Chris"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Finde Chris
        chris = Student.objects.filter(first_name__icontains='Chris').first()
        
        if not chris:
            self.stdout.write(self.style.ERROR("Student 'Chris' nicht gefunden."))
            return
        
        self.stdout.write(f"Gefundener Student: {chris.full_name} (ID: {chris.pk})")
        
        # Heutiges Datum
        today = timezone.localdate()
        
        # Finde alle zukünftigen Lessons für Chris
        lessons = Lesson.objects.filter(
            contract__student=chris,
            date__gte=today
        )
        
        if not lessons.exists():
            self.stdout.write(self.style.SUCCESS(f"Keine zukünftigen Lessons für {chris.full_name} gefunden."))
            return
        
        count = lessons.count()
        self.stdout.write(f"\nGefunden: {count} zukünftige Lesson(s) für {chris.full_name}")
        self.stdout.write(f"Ab Datum: {today}")
        
        if dry_run:
            self.stdout.write("\nZukünftige Lessons:")
            for lesson in lessons.order_by('date', 'start_time')[:20]:  # Zeige erste 20
                self.stdout.write(f"  - {lesson.date} {lesson.start_time} (ID: {lesson.pk})")
            if count > 20:
                self.stdout.write(f"  ... und {count - 20} weitere")
            self.stdout.write(self.style.WARNING("\nDRY-RUN: Keine Lessons wurden gelöscht."))
        else:
            # Lösche die Lessons
            deleted_count, _ = lessons.delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nErfolgreich {deleted_count} zukünftige Lesson(s) gelöscht."
                )
            )

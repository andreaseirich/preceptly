"""
Management command to move all Wednesday lessons for Johann to 18:00.

Usage:
    python manage.py move_johann_wednesdays_to_18 [--dry-run]
"""

from datetime import time

from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_service import RecurringLessonService
from apps.lessons.recurring_utils import get_all_lessons_for_recurring
from apps.students.models import Student
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Moves all Wednesday lessons for Johann to 18:00"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        new_time = time(18, 0)  # 18:00
        
        # Finde Johann
        johann = Student.objects.filter(first_name__icontains='Johann').first()
        
        if not johann:
            self.stdout.write(self.style.ERROR("Student 'Johann' nicht gefunden."))
            return
        
        self.stdout.write(f"Gefundener Student: {johann.full_name} (ID: {johann.pk})")
        
        # Finde alle Lessons für Johann
        all_lessons = Lesson.objects.filter(
            contract__student=johann
        ).select_related('contract')
        
        # Filtere nach Mittwochs (weekday() == 2, da 0=Montag, 2=Mittwoch)
        wednesday_lessons = [l for l in all_lessons if l.date.weekday() == 2]
        
        # Finde alle RecurringLessons für Johann, die Mittwochs haben
        recurring_lessons = RecurringLesson.objects.filter(
            contract__student=johann,
            wednesday=True,
            is_active=True
        ).select_related('contract')
        
        self.stdout.write(f"\nGefunden:")
        self.stdout.write(f"  - {len(wednesday_lessons)} einzelne Lesson(s) an Mittwochs")
        self.stdout.write(f"  - {len(recurring_lessons)} RecurringLesson(s) mit Mittwochs")
        
        if not wednesday_lessons and not recurring_lessons:
            self.stdout.write(self.style.SUCCESS("Keine Lessons gefunden, die den Kriterien entsprechen."))
            return
        
        # Zeige Details
        if wednesday_lessons:
            self.stdout.write(f"\nEinzelne Lessons an Mittwochs:")
            for lesson in wednesday_lessons[:10]:  # Zeige max. 10
                self.stdout.write(f"  - {lesson.date} {lesson.start_time} -> {new_time} (ID: {lesson.pk})")
            if len(wednesday_lessons) > 10:
                self.stdout.write(f"  ... und {len(wednesday_lessons) - 10} weitere")
        
        if recurring_lessons:
            self.stdout.write(f"\nRecurringLessons mit Mittwochs:")
            for recurring in recurring_lessons:
                self.stdout.write(f"  - Serie: {recurring.start_date} bis {recurring.end_date or 'unbegrenzt'}, "
                                f"aktuell {recurring.start_time} -> {new_time} (ID: {recurring.pk})")
                # Zeige Anzahl der betroffenen Lessons
                all_series_lessons = get_all_lessons_for_recurring(recurring)
                wednesday_series_lessons = [l for l in all_series_lessons if l.date.weekday() == 2]
                self.stdout.write(f"    Betroffene Mittwochs-Lessons: {len(wednesday_series_lessons)}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: Keine Änderungen wurden vorgenommen."))
        else:
            with transaction.atomic():
                # 1. Aktualisiere einzelne Lessons
                updated_single_count = 0
                for lesson in wednesday_lessons:
                    lesson.start_time = new_time
                    lesson.save()
                    updated_single_count += 1
                
                # 2. Aktualisiere RecurringLessons und deren Lessons
                updated_recurring_count = 0
                updated_recurring_lessons_count = 0
                
                for recurring in recurring_lessons:
                    # Speichere die ursprüngliche start_time
                    original_start_time = recurring.start_time
                    
                    # Finde alle Lessons dieser Serie BEVOR wir die RecurringLesson ändern
                    all_series_lessons = get_all_lessons_for_recurring(recurring, original_start_time=original_start_time)
                    
                    # Aktualisiere RecurringLesson
                    recurring.start_time = new_time
                    recurring.save()
                    updated_recurring_count += 1
                    
                    # Aktualisiere alle Lessons dieser Serie
                    for lesson in all_series_lessons:
                        # Nur Mittwochs-Lessons aktualisieren
                        if lesson.date.weekday() == 2:
                            lesson.start_time = new_time
                            lesson.save()
                            updated_recurring_lessons_count += 1
                    
                    # Regeneriere Lessons für die Serie (falls nötig)
                    # Dies stellt sicher, dass zukünftige Lessons auch die neue Zeit haben
                    RecurringLessonService.generate_lessons(recurring, check_conflicts=True)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nErfolgreich aktualisiert:\n"
                        f"  - {updated_single_count} einzelne Lesson(s)\n"
                        f"  - {updated_recurring_count} RecurringLesson(s)\n"
                        f"  - {updated_recurring_lessons_count} Lesson(s) aus Serien"
                    )
                )

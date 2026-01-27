"""
Management command to check if lessons data exists in the database.
Run this to diagnose data loss issues.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Check if lessons data exists in the database"

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Check if lessons_lesson table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'lessons_lesson'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                self.stdout.write(
                    self.style.ERROR("❌ Table 'lessons_lesson' does NOT exist!")
                )
                return
            
            # Check row count
            cursor.execute("SELECT COUNT(*) FROM lessons_lesson;")
            count = cursor.fetchone()[0]
            
            if count == 0:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  Table 'lessons_lesson' exists but is EMPTY ({count} rows)")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Table 'lessons_lesson' has {count} rows")
                )
            
            # Check for backup tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND (table_name LIKE '%lesson%backup%' 
                     OR table_name LIKE '%lesson%old%'
                     OR table_name = 'lessons_lesson_backup'
                     OR table_name = 'lessons_lesson_old');
            """)
            backup_tables = cursor.fetchall()
            
            if backup_tables:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Found backup tables: {[t[0] for t in backup_tables]}")
            )
            
            # Check all tables with 'lesson' in name
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE '%lesson%';
            """)
            all_lesson_tables = cursor.fetchall()
            
            self.stdout.write("\nAll tables with 'lesson' in name:")
            for table in all_lesson_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]};")
                table_count = cursor.fetchone()[0]
                self.stdout.write(f"  - {table[0]}: {table_count} rows")

# Generated manually to fix missing lessons_lesson table
# This migration creates the lessons_lesson table if it doesn't exist

from django.db import migrations, models, connection
import django.core.validators
import django.db.models.deletion


def create_lessons_lesson_table_if_not_exists(apps, schema_editor):
    """Create lessons_lesson table if it doesn't exist."""
    with connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'lessons_lesson'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            # Create the table manually
            cursor.execute("""
                CREATE TABLE lessons_lesson (
                    id BIGSERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    start_time TIME NOT NULL,
                    duration_minutes INTEGER NOT NULL CHECK (duration_minutes >= 1),
                    status VARCHAR(20) NOT NULL DEFAULT 'planned',
                    travel_time_before_minutes INTEGER NOT NULL DEFAULT 0,
                    travel_time_after_minutes INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    contract_id BIGINT NOT NULL REFERENCES contracts_contract(id) ON DELETE CASCADE
                );
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX lessons_les_date_e38248_idx ON lessons_lesson(date, start_time);
            """)
            cursor.execute("""
                CREATE INDEX lessons_les_status_ff86f9_idx ON lessons_lesson(status);
            """)


def reverse_create_lessons_lesson_table(apps, schema_editor):
    """Reverse migration - drop table if it exists."""
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS lessons_lesson CASCADE;")


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0006_contract_booking_token_working_hours'),
        ('lessons', '0005_lessondocument'),
    ]

    operations = [
        migrations.RunPython(
            create_lessons_lesson_table_if_not_exists,
            reverse_create_lessons_lesson_table,
        ),
    ]

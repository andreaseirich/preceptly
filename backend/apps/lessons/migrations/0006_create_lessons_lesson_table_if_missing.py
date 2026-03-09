# Generated manually to fix missing lessons_lesson table
# This migration creates the lessons_lesson table if it doesn't exist.
# Uses introspection + schema_editor so it works with SQLite and PostgreSQL.

from django.db import connection, migrations


def create_lessons_lesson_table_if_not_exists(apps, schema_editor):
    """Create lessons_lesson table if it doesn't exist (SQLite + PostgreSQL)."""
    Lesson = apps.get_model("lessons", "Lesson")
    table_name = Lesson._meta.db_table
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
    if any(t.lower() == table_name.lower() for t in tables):
        return
    schema_editor.create_model(Lesson)


def reverse_create_lessons_lesson_table(apps, schema_editor):
    """Reverse migration - drop table if it exists."""
    Lesson = apps.get_model("lessons", "Lesson")
    table_name = Lesson._meta.db_table
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
    if not any(t.lower() == table_name.lower() for t in tables):
        return
    schema_editor.delete_model(Lesson)


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

#!/usr/bin/env python
"""
Quick script to check lessons data in database.
Run this on the server: python check_data.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutorflow.settings')
django.setup()

from django.db import connection

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
        print("❌ Table 'lessons_lesson' does NOT exist!")
        sys.exit(1)
    
    # Check row count
    cursor.execute("SELECT COUNT(*) FROM lessons_lesson;")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print(f"⚠️  Table 'lessons_lesson' exists but is EMPTY ({count} rows)")
    else:
        print(f"✅ Table 'lessons_lesson' has {count} rows")
    
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
        print(f"✅ Found backup tables: {[t[0] for t in backup_tables]}")
    
    # Check all tables with 'lesson' in name
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%lesson%';
    """)
    all_lesson_tables = cursor.fetchall()
    
    print("\nAll tables with 'lesson' in name:")
    for table in all_lesson_tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]};")
            table_count = cursor.fetchone()[0]
            print(f"  - {table[0]}: {table_count} rows")
        except Exception as e:
            print(f"  - {table[0]}: Error - {e}")

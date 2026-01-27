-- Prüfen, ob es Daten in verknüpften Tabellen gibt, die wir nutzen können
SELECT 'Invoice Items' as source, COUNT(*) as count 
FROM billing_invoiceitem 
WHERE lesson_id IS NOT NULL
UNION ALL
SELECT 'Lesson Plans', COUNT(*) 
FROM lesson_plans_lessonplan 
WHERE lesson_id IS NOT NULL
UNION ALL
SELECT 'Recurring Lessons', COUNT(*) 
FROM lessons_recurringlesson;

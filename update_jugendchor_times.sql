-- ============================================
-- SQL-Befehle zum Aktualisieren aller Blockzeiten "Jugendchor"
-- ab dem 02.02. - Startzeit auf 18:45 setzen
-- ============================================
-- WICHTIG: Führen Sie zuerst den SELECT-Befehl aus, um zu sehen, was geändert wird!
-- ============================================

-- 1. ZUERST: Prüfen, welche Blockzeiten geändert werden
--    (Zeigt alle "Jugendchor" Blockzeiten ab 02.02.)
SELECT 
    id,
    title,
    start_datetime,
    end_datetime,
    EXTRACT(EPOCH FROM (end_datetime - start_datetime))/60 as dauer_minuten,
    DATE(start_datetime) as datum,
    TIME(start_datetime) as aktuelle_startzeit,
    TIME(end_datetime) as aktuelle_endzeit
FROM blocked_times_blockedtime
WHERE title = 'Jugendchor'
  AND DATE(start_datetime) >= '2026-02-02'  -- Ab 02.02.2026 (Jahr anpassen falls nötig)
ORDER BY start_datetime;

-- 2. Anzahl der betroffenen Blockzeiten anzeigen
SELECT COUNT(*) as anzahl_blockzeiten
FROM blocked_times_blockedtime
WHERE title = 'Jugendchor'
  AND DATE(start_datetime) >= '2026-02-02';

-- ============================================
-- 3. UPDATE: Startzeit auf 18:45 setzen
--    Die Dauer wird beibehalten (Endzeit wird entsprechend angepasst)
--    WARNUNG: Dieser Befehl kann nicht rückgängig gemacht werden!
-- ============================================
UPDATE blocked_times_blockedtime
SET 
    start_datetime = (DATE(start_datetime) + TIME '18:45:00')::timestamp,
    end_datetime = (DATE(start_datetime) + TIME '18:45:00' + (end_datetime - start_datetime))::timestamp,
    updated_at = NOW()
WHERE title = 'Jugendchor'
  AND DATE(start_datetime) >= '2026-02-02';

-- ============================================
-- Alternative: Wenn Sie die Endzeit auch auf eine bestimmte Zeit setzen möchten
-- (z.B. immer 19:45 als Endzeit):
-- ============================================
-- UPDATE blocked_times_blockedtime
-- SET 
--     start_datetime = (DATE(start_datetime) + TIME '18:45:00')::timestamp,
--     end_datetime = (DATE(start_datetime) + TIME '19:45:00')::timestamp,
--     updated_at = NOW()
-- WHERE title = 'Jugendchor'
--   AND DATE(start_datetime) >= '2026-02-02';

-- ============================================
-- Alternative: Wenn Sie eine feste Dauer verwenden möchten (z.B. immer 1 Stunde):
-- ============================================
-- UPDATE blocked_times_blockedtime
-- SET 
--     start_datetime = (DATE(start_datetime) + TIME '18:45:00')::timestamp,
--     end_datetime = (DATE(start_datetime) + TIME '19:45:00')::timestamp,
--     updated_at = NOW()
-- WHERE title = 'Jugendchor'
--   AND DATE(start_datetime) >= '2026-02-02';

-- ============================================
-- Prüfen nach dem Update:
-- ============================================
-- SELECT 
--     id,
--     title,
--     start_datetime,
--     end_datetime,
--     TIME(start_datetime) as neue_startzeit,
--     TIME(end_datetime) as neue_endzeit
-- FROM blocked_times_blockedtime
-- WHERE title = 'Jugendchor'
--   AND DATE(start_datetime) >= '2026-02-02'
-- ORDER BY start_datetime;

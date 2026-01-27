-- ============================================
-- SQL-Befehle zum Aktualisieren aller Blockzeiten "Bibelstunde"
-- ab dem 02.02. - Startzeit auf 16:15 und Dauer auf 120 Minuten setzen
-- ============================================
-- WICHTIG: Führen Sie zuerst den SELECT-Befehl aus, um zu sehen, was geändert wird!
-- ============================================

-- 1. ZUERST: Prüfen, welche Blockzeiten geändert werden
--    (Zeigt alle "Bibelstunde" Blockzeiten ab 02.02.)
SELECT 
    id,
    title,
    start_datetime,
    end_datetime,
    EXTRACT(EPOCH FROM (end_datetime - start_datetime))/60 as aktuelle_dauer_minuten,
    DATE(start_datetime) as datum,
    TIME(start_datetime) as aktuelle_startzeit,
    TIME(end_datetime) as aktuelle_endzeit,
    (DATE(start_datetime) + TIME '16:15:00')::timestamp as neue_startzeit,
    (DATE(start_datetime) + TIME '16:15:00' + INTERVAL '120 minutes')::timestamp as neue_endzeit
FROM blocked_times_blockedtime
WHERE title = 'Bibelstunde'
  AND DATE(start_datetime) >= '2026-02-02'  -- Ab 02.02.2026 (Jahr anpassen falls nötig)
ORDER BY start_datetime;

-- 2. Anzahl der betroffenen Blockzeiten anzeigen
SELECT COUNT(*) as anzahl_blockzeiten
FROM blocked_times_blockedtime
WHERE title = 'Bibelstunde'
  AND DATE(start_datetime) >= '2026-02-02';

-- ============================================
-- 3. UPDATE: Startzeit auf 16:15 setzen und Dauer auf 120 Minuten
--    WARNUNG: Dieser Befehl kann nicht rückgängig gemacht werden!
-- ============================================
UPDATE blocked_times_blockedtime
SET 
    start_datetime = (DATE(start_datetime) + TIME '16:15:00')::timestamp,
    end_datetime = (DATE(start_datetime) + TIME '16:15:00' + INTERVAL '120 minutes')::timestamp,
    updated_at = NOW()
WHERE title = 'Bibelstunde'
  AND DATE(start_datetime) >= '2026-02-02';

-- ============================================
-- Prüfen nach dem Update:
-- ============================================
SELECT 
    id,
    title,
    start_datetime,
    end_datetime,
    EXTRACT(EPOCH FROM (end_datetime - start_datetime))/60 as neue_dauer_minuten,
    DATE(start_datetime) as datum,
    TIME(start_datetime) as neue_startzeit,
    TIME(end_datetime) as neue_endzeit
FROM blocked_times_blockedtime
WHERE title = 'Bibelstunde'
  AND DATE(start_datetime) >= '2026-02-02'
ORDER BY start_datetime;

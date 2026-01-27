# Migration Safety Guide

## Wichtige Regeln für sichere Migrationen

### 1. IMMER Backups vor Migrationen erstellen

**Vor jeder Migration:**
```bash
# Auf Railway: PostgreSQL Service → Backups → Create Backup
# Oder manuell:
pg_dump -U user database_name > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Migrationen testen

**Lokale Test-Datenbank:**
```bash
# Lokale Kopie der Produktionsdatenbank erstellen
pg_dump production_db > test_db.sql
psql test_db < test_db.sql

# Migrationen auf Test-Datenbank ausführen
python manage.py migrate

# Prüfen, ob Daten noch vorhanden sind
python manage.py check_lessons_data
```

### 3. Datenmigrationen bei Modell-Änderungen

**Wenn ein Modell umbenannt wird (z.B. Lesson → Session):**

1. **NICHT** das alte Modell löschen
2. **Zuerst** Daten migrieren
3. **Dann** das alte Modell löschen

**Beispiel für sichere Migration:**
```python
# Migration 1: Neues Modell erstellen
migrations.CreateModel(name='Session', ...)

# Migration 2: Daten kopieren
def copy_lessons_to_sessions(apps, schema_editor):
    Lesson = apps.get_model('lessons', 'Lesson')
    Session = apps.get_model('lessons', 'Session')
    
    for lesson in Lesson.objects.all():
        Session.objects.create(
            contract=lesson.contract,
            date=lesson.date,
            start_time=lesson.start_time,
            # ... alle Felder kopieren
        )

# Migration 3: Foreign Keys aktualisieren
# Migration 4: Altes Modell löschen (nur wenn alles migriert ist)
```

### 4. Checkliste vor Produktions-Migrationen

- [ ] Backup erstellt
- [ ] Migration auf Test-Datenbank getestet
- [ ] Datenprüfung nach Migration durchgeführt
- [ ] Rollback-Plan vorhanden
- [ ] Wartungsfenster geplant (falls nötig)

### 5. Automatische Backups einrichten

**Railway:**
- PostgreSQL Service → Backups → Enable automatic backups
- Täglich oder wöchentlich

**Manuell (Cron):**
```bash
0 2 * * * pg_dump -U user database > /backups/db_$(date +\%Y\%m\%d).sql
```

## Was ist schiefgelaufen?

Die Migration hat:
1. `Session` erstellt (neue Tabelle `lessons_lesson`)
2. `Lesson` gelöscht (alte Tabelle `lessons_lesson` wurde gelöscht)
3. **ABER:** Die Daten wurden nicht migriert, bevor `Lesson` gelöscht wurde

**Richtige Reihenfolge wäre gewesen:**
1. `Session` erstellen
2. Daten von `Lesson` nach `Session` kopieren
3. Foreign Keys aktualisieren
4. `Lesson` löschen (nur wenn alles migriert ist)

## Wiederherstellung

Falls Daten verloren gehen:
1. Railway Backups prüfen
2. Neuestes Backup wiederherstellen
3. Migrationen korrigieren
4. Erneut migrieren

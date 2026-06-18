# Product Requirements Document — Tutorflow (Preceptly)

## Produktvision
Tutorflow ist eine Verwaltungsplattform für unabhängige Tutoren. Sie ermöglicht es Tutoren, ihre Schüler, Verträge, Stunden, Zahlungen und KI-gestützte Unterrichtsplanung zentral zu verwalten und zu skalieren.

## Kernfunktionalität

### 1. Schülerverwaltung (`students`)
- Schüler anlegen, bearbeiten, archivieren
- Kontaktdaten, Elterninfo, Lernziele
- Schüler-Tutor-Zuordnung

### 2. Vertragsverwaltung (`contracts`)
- Verträge erstellen (Stundenzahl, Satz, Laufzeit)
- Vertragsstatus (aktiv, abgelaufen, gekündigt)
- Vertragshistorie und Archivierung

### 3. Stundenverwaltung (`lessons`)
- Stunden anlegen, absagen, verschieben
- Stundendauer, Thema, Notizen
- Abrechnung basierend auf Stundensatz

### 4. Unterrichtsplanung (`lesson_plans`)
- KI-gestützte Lektionsplanung (App `ai`)
- Templates für verschiedene Fachgebiete
- Speicherung und Wiederverwendung

### 5. Blockierungszeiten (`blocked_times`)
- Tutoren blockieren Zeiten (Urlaub, private Termine)
- Automatische Übernahme in Verfügbarkeitslogik

### 6. Abrechnung (`billing`)
- Rechnungsverwaltung nach Leistung
- Zahlungsstatus (ausstehend, bezahlt)
- Zahlungsintegrationen (Stripe, PayPal, etc.)

### 7. Portal (`portal`)
- Schüler-Self-Service (Stundenblatt, Downloads)
- Tutor-Dashboard (Übersicht aller Funktionen)
- Kommunikation (Nachrichten, Benachrichtigungen)

### 8. KI-Integration (`ai`)
- Leistungsanalyse
- Individuelle Lektionsempfehlungen
- Automatische Zusammenfassungen

## Technischer Stack
- **Backend:** Django 5.x, Python 3.12
- **Datenbank:** PostgreSQL
- **Frontend:** Tailwind CSS (CDN)
- **Infrastruktur:** Docker, Railway
- **Core-App:** Zentrale Geschäftslogik und Authentifizierung

## Zielgruppen
1. **Tutoren:** Unabhängige, selbstständige Pädagogen
2. **Schüler/Eltern:** Via Portal (Lesezugriff, Fortschritt, Rechnungen)
3. **Administratoren:** Plattformsupport und Monitoring

## Nicht im Scope
- Videountericht-Integration (nur Verwaltung)
- Mobile App (responsive Web)
- Echtzeit-Unterrichtsmetriken
- Lernmanagementsystem (LMS) für Lernplattform

## Erfolgsmetriken
- Tutor-Onboarding < 5 Min
- 95% Verfügbarkeit
- Abrechnungsgenauigkeit 99,9%
- NPS > 60
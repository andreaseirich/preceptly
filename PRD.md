# Product Requirements Document — Preceptly

**Stand:** 24.09.2026 — beschreibt, was live ist. Geplantes steht ausdrücklich als „geplant".

## Produktvision

Preceptly ist die Verwaltungsplattform für selbständige Nachhilfelehrer. Sie
nimmt ihnen die Verwaltung ab — Termine, Verträge, Rechnungen, Einnahmen — und
gibt Schülern und Eltern einen eigenen Zugang, über den sie Termine sehen,
buchen und mit dem Tutor schreiben können.

Ziel: zwei bis drei Stunden Verwaltung pro Woche einsparen, ohne dass ein Tutor
ein allgemeines CRM oder mehrere Werkzeuge zusammenstecken muss.

## Zielgruppen

1. **Tutoren** — selbständig, allein oder über Institute tätig
2. **Schüler** — über das Portal: Stunden, Hausaufgaben, Buchung, Nachrichten
3. **Eltern** — über das Portal: Überblick über ein oder mehrere Kinder
4. **Betreiber** — Moderation von Bewertungen, Zugriffsstatistik

## Kernfunktionen (live)

### Schüler und Verträge
- Schüler sind **Verträge** (`contracts.Contract`): Stundensatz, Laufzeit, Fächer, Kontakt- und Elterndaten
- Institute als Auftraggeber, auch mit abweichendem Rechnungsempfänger
- Verträge aktiv/inaktiv schalten, Familien verknüpfen
- Dokumente je Schüler (mit Prüfung des Dateiinhalts)

### Stunden und Kalender
- Einzelstunden anlegen, verschieben, absagen; Monats- und Wochenansicht
- **Serientermine** mit Massenbearbeitung und Ende nach Vertragslaufzeit
- **Konfliktprüfung**: Überschneidungen, Fahrzeiten, Sperrzeiten
- **Sperrzeiten** (Urlaub, private Termine)
- Buchung durch Schüler läuft über das **Portal** (siehe unten). Die frühere öffentliche Buchungsseite (`/lessons/booking/<token>/`) wurde mit dem Tarif-Umbau aus der Oberfläche genommen, Adresse und View bestehen aber noch — und brechen mit einem Serverfehler ab, sobald der Schüler in der gezeigten Woche einen Termin hat (Stand 24.09.2026, Entscheidung offen: entfernen oder reparieren)
- **iCloud-Kalender-Sync** (CalDAV): zukünftige Stunden werden übertragen, vergangene entfernt; Konflikte sichtbar

### Abrechnung und Einnahmen
- Rechnungen aus gehaltenen Stunden, als PDF; Status offen/versendet/bezahlt
- Einnahmenübersicht nach bezahlten **Einheiten** je Monat
- Ausgaben, EÜR-Export, Steuerjahr-Übersicht, Berichte

### Portal für Schüler und Eltern
- Eigener Login, Aktivierung per E-Mail-Einladung, Passwort zurücksetzen
- Kommende und vergangene Stunden, Hausaufgaben, Fortschrittsnotizen
- Stunden buchen, verschieben, absagen; Serien verwalten
- Nachrichten mit dem Tutor
- Kalenderfeed (iCal) mit erneuerbarem Link
- Push-Benachrichtigungen, als App installierbar (PWA)
- Details: `docs/features/feat-portal.md`

### Video-Meetings
- Meeting-Raum je Stunde, direkt im Browser (WebRTC)
- Eigener TURN-Server für Verbindungen hinter NAT, Zugangsdaten nur 8 Stunden gültig
- Dokumente im Raum teilen, PDF-Anzeige mit selbst ausgeliefertem pdf.js
- Es wird nichts aufgezeichnet

### KI-Unterrichtsplanung
- Unterrichtsplan für eine Stunde erzeugen, neu erzeugen, speichern
- Zusätzlicher Kontext als Text oder PDF
- Namen, E-Mail-Adressen und Telefonnummern werden vor dem Versand geschwärzt
- Sprachmodell selbst gehostet (über Tailscale), ohne Schlüssel Mock-Modus

### Konto, Recht und Betrieb
- Beim Abo-Abschluss wird die Zustimmung zum vorzeitigen Leistungsbeginn (Widerrufsverzicht) mit Zeitpunkt gespeichert
- Rechtstexte über e-Recht24, Widerrufs-Button, AVV mit Zustimmung
- Zweisprachig (Deutsch/Englisch)
- Demo-Konten zum Ausprobieren

## Tarife

| Tarif | Umfang |
|---|---|
| **Free** | Stunden, Kalender, Konflikte, Rechnungen — für Konten ab dem 02.07.2026 höchstens 5 Schüler und 8 Rechnungen pro Monat (durchgesetzt) |
| **Starter** | + Serientermine, Sperrzeiten, Dokumente, erweiterte Abrechnung, Schüler-Portal, Portal-Buchung |
| **Pro** | + Eltern-Portal, Meeting-Räume, KI-Unterrichtspläne, EÜR-Export, Berichte |
| **Business** | alles aus Pro |

Abos laufen über Stripe Checkout, Verwaltung über das Stripe-Kundenportal.
Maßgeblich ist `backend/apps/core/feature_flags.py`.

**Abweichung (Stand 24.09.2026):** Die Preisseite bewirbt Starter mit „3 Dokumente je Schüler" und „3 Portal-Buchungen pro Monat", Pro mit „unbegrenzten Dokumenten". Die Grenzen sind in `feature_flags.py` als `STARTER_DOCUMENT_LIMIT` und `STARTER_PORTAL_BOOKING_MONTHLY_LIMIT` definiert, werden aber **nirgends durchgesetzt** — Starter-Kunden haben beides derzeit unbegrenzt. Entscheidung offen: Grenzen einbauen oder von der Preisseite nehmen.

**Wichtig:** Stripe rechnet nur die Abos der Tutoren ab. Zahlungen der Schüler
an den Tutor laufen außerhalb von Preceptly; Preceptly erstellt die Rechnung
und hält den Zahlungsstatus fest.

## Nicht im Scope

- Native Mobile-App — stattdessen responsive Web und PWA
- Lernmanagementsystem (Kurse, Aufgaben einreichen, Noten)
- Aufzeichnung von Video-Meetings
- Zahlungsabwicklung zwischen Schülern und Tutoren
- Echtzeit-Unterrichtsmetriken

## Erfolgsmetriken

- Tutor-Onboarding < 5 Min
- 95 % Verfügbarkeit
- Abrechnungsgenauigkeit 99,9 %
- NPS > 60

## Technik

Siehe `CLAUDE.md` (Stack, Struktur, Konventionen) und `docs/ARCHITECTURE.md`.

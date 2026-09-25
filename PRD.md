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
- Buchung durch Schüler läuft über das **Portal** (siehe unten). Die frühere öffentliche Buchungsseite ist seit 24.09.2026 entfernt.
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
| **Free** | Stunden, Kalender, Konflikte, Rechnungen — für Konten ab dem 02.07.2026 höchstens 5 Schüler und 8 Rechnungen pro Monat. Keine Dokumente, keine Portal-Buchung |
| **Starter** | + Serientermine, Sperrzeiten, erweiterte Abrechnung, Schüler-Portal; **höchstens 3 Dokumente je Schüler**, **höchstens 3 Portal-Buchungen je Monat** (nur Einzeltermine) |
| **Pro** | + unbegrenzte Dokumente, unbegrenzte Portal-Buchungen und **Serien im Portal**, Eltern-Portal, Meeting-Räume, KI-Unterrichtspläne, EÜR-Export, Berichte |
| **Business** | alles aus Pro, dazu bevorzugter Support und früher Zugang zu neuen Funktionen |

Abos laufen über Stripe Checkout, Verwaltung über das Stripe-Kundenportal.
Maßgeblich ist `backend/apps/core/feature_flags.py`.

**Was der Code durchsetzt (Stand 24.09.2026):**

| Grenze | Wo |
|---|---|
| Free: 5 Schüler, 8 Rechnungen/Monat (Konten ab 02.07.2026) | `students/views.py`, `billing/views.py` |
| Dokumente: Free keine, Starter 3 je Schüler — beim Tutor und im Portal | `document_limit_reached()` |
| Portal-Buchungen: Free keine, Starter 3 je Tutor und Kalendermonat, gezählt nach Anlagedatum | `portal_booking_limit_reached()` |
| Serien im Portal selbst anlegen: erst ab Pro | `Feature.FEATURE_PORTAL_RECURRING` |
| KI-Pläne, Berichte, erweiterte Abrechnung | `user_has_feature()` in den jeweiligen Views |
| Sperrzeiten anlegen/ändern (Starter) | `BlockedTimeCreateView`, `BlockedTimeUpdateView` |
| Serien anlegen/ändern/fortschreiben, auch über das Stunden-Formular (Starter) | Serien-Views, `SessionForm.series_locked` |
| Portal-Einladungen (Starter) | `PortalInviteView`, `PortalInviteResendView` |
| Familien-Zugang: mehrere Kinder an einem Portal-Konto (Pro) | `FamilyLinkView`, Einladung an vorhandene E-Mail |
| Meeting-Raum öffnen (Pro) | `StartMeetingView` |

Seit 25.09.2026 setzt der Code **alle** Tarif-Zuordnungen der Preisseite durch.
Gemeinsamer Baustein: `apps/core/tier_gate.py`; für Vorlagen der
Context-Processor `plan_features` (`{% if plan.meetings %}` usw.).

**Regel für gesperrte Funktionen:** Neues anlegen und Ändern erst ab dem Tarif.
Ansehen, Absagen und Löschen bleiben immer möglich, bestehende Portal-Konten
bleiben aktiv und können sich weiter anmelden. Läuft ein Abo aus, verlieren
Schüler und Eltern also nicht, was schon da ist — sie können nur nichts Neues
buchen oder hochladen.

**„Eltern-Portal" heißt im Code Familien-Zugang:** Es gibt keine getrennten
Eltern-Konten; ein Portal-Konto gehört zu einem Vertrag. Hängen mehrere Kinder
an einem Konto, zeigt das Portal die Familien-Übersicht. Im Starter-Tarif
braucht deshalb jedes Kind eine eigene E-Mail-Adresse.

**Ausnahme:** Der iCloud-Kalender-Sync legt weiterhin Sperrzeiten an, auch im
Free-Tarif — er spiegelt Termine aus dem Kalender, damit nichts doppelt gebucht
wird. Gesperrt ist nur das eigene Anlegen über die Oberfläche.

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

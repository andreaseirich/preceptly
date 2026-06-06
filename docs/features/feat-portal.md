# Feature: Eltern/Schüler-Portal

## Ziel

Das Eltern/Schüler-Portal gibt Eltern und Schülern einen dedizierten, sicheren Zugang zu relevanten Unterrichtsinformationen und ermöglicht die bidirektionale Kommunikation mit dem Tutor. Eltern erhalten Einblick in den Fortschritt ihrer Kinder und anstehende Stunden, Schüler können ihre Hausaufgaben und Unterrichtsmaterialien einsehen.

## Nutzer-Rollen

| Rolle | Sicht | Aktionen |
|-------|-------|----------|
| **Tutor** | Administrationsoberfläche | Einladungslinks generieren, ProgressNotes erstellen, Hausaufgaben/Meeting-Links setzen, Nachrichten lesen + antworten |
| **Elternteil** | Portal-Dashboard | Alle verknüpften Kinder sehen, Fortschrittsnotizen lesen, Stundenplan einsehen, mit Tutor kommunizieren |
| **Schüler** | Portal-Dashboard | Eigene kommende Stunden, Hausaufgaben, Unterrichtsmaterialien, direktes Messaging mit Tutor |

## Datenmodell

| Modell | Schlüsselfelder | Beziehung |
|--------|-----------------|-----------|
| **PortalUser** | user (OneToOne → User), role (parent/student), tutor (FK → User), created_at | Basis für Portal-Accounts |
| **StudentPortalLink** | portal_user (FK), student (OneToOne), invite_token (UUID), is_active | Verknüpfung Schüler ↔ Portal |
| **ParentStudentLink** | parent (FK → PortalUser), student (FK → Student) | M2M: mehrere Eltern/Kinder |
| **ProgressNote** | student (FK), tutor (FK → User), date, text, created_at | Fortschrittsnotizen pro Schüler |
| **PortalMessage** | sender_portal_user (FK), sender_is_tutor, student (FK), text, created_at, read_by_tutor, read_by_portal | Nachrichten Tutor ↔ Portal |

**Erweiterungen bestehender Modelle:**
- `lessons.Session`: `homework` (TextField), `meeting_url` (CharField)

## URL-Struktur

| URL | Beschreibung | Rolle |
|-----|--------------|-------|
| `/portal/` | Dispatch (Weiterleitung je nach Rolle) | Alle |
| `/portal/login/` | Portal-Login | Anonym |
| `/portal/logout/` | Portal-Logout | Authentifiziert |
| `/portal/student/` | Schüler-Startseite (kommende Stunden, Hausaufgaben) | Schüler |
| `/portal/student/lessons/` | Stundenhistorie | Schüler |
| `/portal/parent/` | Eltern-Startseite (Kinder-Übersicht) | Eltern |
| `/portal/parent/<pk>/` | Detail-Ansicht eines Kindes | Eltern |
| `/portal/messages/<student_pk>/` | Nachrichtenthread | Eltern/Schüler |

## Implementierungs-Status

- [x] Modelldesign und DB-Architektur
- [x] PortalUser, StudentPortalLink, ParentStudentLink, ProgressNote, PortalMessage
- [x] Session homework/meeting_url Felder + Migrationen
- [x] App-Struktur (urls.py, views.py, settings.py Integration)
- [ ] PortalLoginView + Authentication
- [ ] Student/Parent HomeViews + Templates
- [ ] Nachrichten-Views + Templates
- [ ] Tutor-seitige UI (Einladungslinks, ProgressNotes, Session-Formular)
- [ ] Sicherheitstests (Cross-Tutor-Zugriff)
- [ ] Deployment

## Offene Punkte / TODOs

- Einladungs-E-Mail-Template und Versand
- Ungelesene-Nachrichten-Badge im Tutor-Menü
- Mobile Responsive Design für Portal-Templates
- Datenschutz: Eltern-Zugriff auf Schüler-Daten (Einwilligung dokumentieren)

# Feature: Eltern/Schüler-Portal

**Stand:** 24.09.2026 — live auf https://preceptly.de/portal/

## Ziel

Schüler und Eltern bekommen einen eigenen, sicheren Zugang zu allem, was ihre
Stunden betrifft: Termine sehen, buchen, verschieben und absagen, Hausaufgaben
und Fortschritt, Dokumente, Nachrichten an den Tutor. Der Tutor spart sich
dadurch Abstimmung per Telefon und Messenger.

## Nutzer-Rollen

| Rolle | Sicht | Aktionen |
|-------|-------|----------|
| **Tutor** | Verwaltungsoberfläche | Portal-Einladung verschicken, Fortschrittsnotizen, Hausaufgaben und Meeting-Links setzen, Nachrichten beantworten |
| **Schüler** | Portal | Eigene Stunden, Hausaufgaben, Dokumente, Buchung, Serien, Nachrichten, Meeting beitreten |
| **Elternteil** | Portal | Alle verknüpften Kinder, Fortschritt, Kalender je Kind, Nachrichten (Tarif Pro) |

Ein Portal-Konto kann mehrere Verträge verwalten (Familien-Zugang): Der Tutor
verknüpft weitere Kinder mit demselben Konto.

## Datenmodell

Schüler sind **Verträge** (`contracts.Contract`) — ein eigenes Schüler-Modell
gibt es nicht mehr.

| Modell | Schlüsselfelder | Beziehung |
|--------|-----------------|-----------|
| **PortalUser** | `user` (1:1 → User), `role` (parent/student), `tutor` (→ User), `ical_feed_token` | Basis jedes Portal-Kontos |
| **ParentStudentLink** | `parent` (→ PortalUser), `contract` (→ Contract), Einladungs- und Reset-Token | **Aktuelle** Verknüpfung Konto ↔ Vertrag, auch für Schüler |
| **StudentPortalLink** | `portal_user` (1:1), `contract` (1:1), Einladungs- und Reset-Token | **Alt-Zugänge**; neue Einladungen legen sie nicht mehr an, der Login findet sie aber weiterhin |
| **ProgressNote** | `contract`, `tutor`, `text`, `date` | Fortschrittsnotizen |
| **PortalMessage** | `sender_portal_user`, `sender_is_tutor`, `contract`, `text`, `read_by_tutor`, `read_by_portal` | Nachrichten Tutor ↔ Portal |

Erweiterungen an `lessons.Session`: `homework`, `meeting_url`.

**E-Mail-Eindeutigkeit:** Ein Login wird über die E-Mail des Django-Users oder —
bei Alt-Zugängen — über die Vertrags-E-Mail gefunden. `apps/portal/identity.py`
stellt sicher, dass keine E-Mail zwei Konten gleichzeitig erreicht.

## URL-Struktur

| URL | Zweck |
|-----|-------|
| `/portal/` | Weiterleitung je nach Rolle |
| `/portal/login/`, `/portal/logout/` | Anmeldung (gedrosselt pro IP und pro Konto) |
| `/portal/activate/<token>/` | Einladung annehmen, Passwort setzen |
| `/portal/password-reset/`, `…/confirm/<token>/` | Passwort zurücksetzen |
| `/portal/student/`, `/portal/student/lessons/`, `…/<pk>/` | Schüler: Übersicht, Stundenliste, Stunde im Detail |
| `/portal/parent/`, `/portal/parent/<student_pk>/` | Eltern: Übersicht, Kind im Detail |
| `/portal/calendar/`, `…/week/` | Kalender (Monat, Woche) |
| `/portal/calendar/<student_pk>/`, `…/week/` | Kalender eines Kindes (Eltern) |
| `/portal/book/<student_pk>/`, `/portal/availability/<student_pk>/` | Stunde buchen, freie Zeiten |
| `/portal/session/<pk>/cancel/`, `…/reschedule/` | Stunde absagen, verschieben |
| `/portal/recurring/<student_pk>/`, `…/create/…`, `…/<pk>/cancel/` | Serien verwalten |
| `/portal/messages/<student_pk>/` | Nachrichten |
| `/portal/documents/<student_pk>/`, `…/<doc_pk>/download/` | Dokumente |
| `/portal/meeting/<lesson_pk>/`, `…/status/` | Warteraum vor dem Meeting |
| `/portal/profile/` | Kontaktdaten, Passwort, Benachrichtigungen |
| `/portal/profile/calendar-feed/renew/` | Kalenderfeed-Link erneuern |
| `/portal/calendar-feed/<token>.ics` | Kalenderfeed (Token ist die Anmeldung) |
| `/portal/push/subscribe/`, `…/unsubscribe/` | Push-Benachrichtigungen |
| `/portal/faq/` | Hilfe |

Einstieg ohne Konto: Link „Zum Portal-Login" auf der Startseite und unter dem
Tutor-Login; der Portal-Login verlinkt zurück zum Tutor-Login.

## Tarife

| Funktion | ab Tarif |
|---|---|
| Schüler-Portal, Portal-Buchung | Starter |
| Eltern-Portal, Meeting-Räume | Pro |

Maßgeblich ist `backend/apps/core/feature_flags.py`.

## Einladungsflow

1. Tutor verschickt die Einladung auf der Schülerseite (E-Mail aus dem Vertrag oder frei eingegeben).
2. Gibt es schon ein Portal-Konto mit dieser Adresse **beim selben Tutor**, wird der Vertrag nur verknüpft (Familien-Zugang). Bei einem anderen Tutor: allgemeine Fehlermeldung, keine Auskunft über das fremde Konto.
3. Sonst: neues Konto, `ParentStudentLink` mit Einladungs-Token, E-Mail über `portal/email_service.py`.
4. Empfänger öffnet `/portal/activate/<token>/`, setzt sein Passwort und ist angemeldet.

E-Mail-Versand und alle Variablen: [`docs/operations/railway-env-vars.md`](../operations/railway-env-vars.md).

## Sicherheit

- Login gedrosselt: pro IP und zusätzlich pro E-Mail (5 Versuche in 5 Minuten), Antwort 429 mit `Retry-After`
- Zugriff immer über die Verknüpfung Konto ↔ Vertrag geprüft; Tests gegen Zugriff über Tutor-Grenzen hinweg: `test_booking_flow.py`, `test_ical_feed.py`, `test_email_uniqueness.py`, `students/test_portal_invite.py`
- Uploads werden am Dateiinhalt geprüft, nicht nur an der Endung

## Offene Punkte

- **Datenschutz Minderjähriger:** Einwilligung für den Eltern-Zugriff auf Schülerdaten dokumentieren — Frage für die rechtliche Prüfung.

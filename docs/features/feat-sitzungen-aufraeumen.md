# Abgelaufene Login-Sitzungen automatisch löschen

**Stand:** 28.10.2026 · Auftrag von Andreas: „Die abgelaufenen Sessions könnten gelöscht werden, aber man sollte vorher
prüfen, ob alle anderen Funktionen dann trotzdem noch gut laufen (z. B. Rechnungen, Steuern, etc.).“

## Begriff: zwei verschiedene „Session“

| | Was es ist | Betroffen? |
|---|---|---|
| `django.contrib.sessions.models.Session` (Tabelle `django_session`) | Login-Sitzung im Browser: Anmeldung und kleine Komfort-Zustände | **ja**, nur abgelaufene |
| `apps.lessons.models.Session` | eine **Stunde** (Unterrichtseinheit), daran hängen Rechnungen, Einnahmen und Steuern | **nein**, nie angefasst |

## Anlass

Django räumt abgelaufene Sitzungen nicht von selbst auf (dafür gibt es den Befehl `clearsessions`, der regelmäßig laufen
müsste). Es gibt keinen Zeitplaner. In der Produktion lagen am 28.10.2026 **159 Sitzungen, 148 davon abgelaufen** (die älteste
vom 31.01.2026).

## Vorab geprüft (Andreas: „vorher prüfen“)

Code und echte Produktionsdaten, nur lesend:

- **Sitzungs-Backend:** Django-Standard (Datenbank, `SESSION_COOKIE_AGE` 14 Tage, PostgreSQL).
- **Kein Zugriff auf die Tabelle im Code**, kein Modell und **keine Datenbank-Beziehung** (Fremdschlüssel) verweist darauf.
  Das Zugriffsprotokoll `RequestLog` speichert nur einen **Hash** des Sitzungsschlüssels, keinen Verweis.
- **Was in der Sitzung liegt:** `portal_user_id` (Portal-Anmeldung), `last_calendar_*` (zuletzt gesehene Kalenderansicht),
  `referral_code` (während der Registrierung), `dev_stats_authed` (Statistikseite, 8 Stunden). Keine Rechnungen, Steuern,
  Stunden oder Verträge.
- **Eine abgelaufene Sitzung gilt für Django ohnehin als nicht vorhanden:** Wer sie hatte, muss sich neu anmelden, mit oder
  ohne die Zeile in der Datenbank. Gültige Sitzungen werden nicht berührt, niemand wird abgemeldet.
- **Tests** (`apps/core/tests/test_session_cleanup.py`): Nach dem Aufräumen laufen Dashboard, Rechnungsliste und
  -details, Einnahmen, Steuerjahr, EÜR (Seite und PDF) und die Portal-Buchung mit einer gültigen Sitzung unverändert; Zahl der
  Stunden, Verträge, Rechnungen und Ausgaben bleibt gleich; eine abgelaufene Sitzung verhält sich vor und nach dem Löschen
  gleich (Weiterleitung zur Anmeldung).

## Verhalten

Einmal am Tag (zusammen mit dem Aufräumen des Zugriffsprotokolls, `RequestLogMiddleware._maybe_purge`) löscht
`purge_expired_sessions()` alle Sitzungen mit `expire_date` in der Vergangenheit, genau wie `clearsessions`. Beide
Aufräumarbeiten laufen unabhängig: Ein Fehler bei der einen verhindert die andere nicht, und ein Fehler beim Aufräumen
verhindert nie eine Antwort. Von Hand geht es mit `python manage.py clearsessions`.

## Code

| Teil | Ort |
|---|---|
| Löschen | `apps/core/session_cleanup.py` |
| Täglicher Aufruf | `apps/core/middleware.py` (`_maybe_purge`) |
| Tests | `apps/core/tests/test_session_cleanup.py` |

## Nicht geändert

Konten werden weiterhin **nicht** automatisch gelöscht (inaktive, nie bestätigte oder Bot-Konten). Dafür fehlt ein Löschkonzept;
Rechnungen müssen aus steuerlichen Gründen aufbewahrt werden. Offener Punkt für Anwalt und Steuerberater.

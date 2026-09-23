# Externer Code-Review 22.09.2026 — Befunde und Umsetzung

**Quelle:** Code-Review von außen (Datei `preceptly-codereview-2026-09-22.md`)
**Bearbeitet:** 22.–23.09.2026
**Stand:** 10 von 10 Befunden erledigt, P3 bis auf einen Punkt erledigt.
Offen bleibt bewusst nur das Scharfschalten der Content-Security-Policy.

## P1 — zeitnah beheben

| # | Befund | Umsetzung |
|---|--------|-----------|
| 1 | Meeting-Raum lädt pdf.js 3.11.174 vom CDN, betroffen von CVE-2024-4367; Eltern können PDFs hochladen, die der Tutor im Raum öffnet | `isEvalSupported: false` an beiden `getDocument`-Aufrufen (`7e8a6f2`); pdf.js auf 6.3.289 gehoben und aus den eigenen Static-Files ausgeliefert statt vom CDN (`f8f34dc`); CSP im Melde-Modus (`e2c1fde`) |
| 2 | Rate-Limits zählten pro Proxy statt pro Besucher — zehn Anfragen pro Minute konnten alle aussperren | `RATELIMIT_IP_META_KEY` nutzt jetzt dieselbe Client-IP-Ermittlung wie die Login-Drosselung (`7e8a6f2`). Live geprüft: 10 Versuche vom ai-server → 11. Versuch 429, gefälschter `X-Forwarded-For` wirkungslos, anderer Rechner unbetroffen |
| 3 | Dependabot-Aktualisierungen wurden vor den Tests zusammengeführt | Branch-Schutz mit Pflicht-Checks (`test`, `hygiene`); CI läuft jetzt auch bei Änderungen an `requirements*.txt` (`446b47d`); Dependabot nutzt `versioning-strategy: increase-if-necessary`, damit Untergrenzen korrekt als Patch/Minor erkannt werden (`257229b`) |

## P2 — sinnvoll, nicht dringend

| # | Befund | Umsetzung |
|---|--------|-----------|
| 4 | Keine Content-Security-Policy | Richtlinie im Melde-Modus aktiv (`e2c1fde`), siehe `docs/operations/content-security-policy.md`. **Scharfschalten steht noch aus** — erst die Meldungen auswerten |
| 5 | Portal-Login ohne Drosselung pro Konto | Zusätzliche Drosselung pro E-Mail-Adresse, fünf Versuche in fünf Minuten (`ffbe7df`) |
| 6 | L4 aus dem Juli-Audit nur teilweise behoben | `apps/portal/identity.py` prüft beide Anmeldewege — Django-User **und** Vertrags-E-Mail eines `StudentPortalLink`; benutzt in Profiländerung und Einladung (`ca8a255`) |
| 7 | TURN-Zugangsdaten statisch und für jeden Teilnehmer sichtbar | Kurzlebige Zugangsdaten nach dem TURN-REST-Verfahren, 8 Stunden gültig (`8bea6e0`); coturn am 23.09. auf `use-auth-secret` umgestellt und geprüft, siehe `docs/operations/turn-server.md` |
| 8 | Kalenderfeed: Token nicht erneuerbar, Notizen landen in fremden Kalendern | Feed-Link erneuerbar, Notizfeld ehrlich beschriftet (`21fd9af`) |
| 9 | Dokumentation hinkt dem Code hinterher | Vollständige Liste der Umgebungsvariablen (`1546885`), neue Betriebsdoku zu TURN und CSP, Doku-Index ergänzt (`2a48c64`), dieser Bericht |
| 10 | Doppelte Dekoratoren an der öffentlichen Buchung | Entfernt, dazu ein doppeltes `@csrf_exempt` am Stripe-Webhook (`7e8a6f2`) |

## P3 — Aufräumen

| Punkt | Umsetzung |
|-------|-----------|
| `StartMeetingView` ändert per GET den Zustand | Raum wird nur noch per POST aus einem CSRF-geschützten Formular geöffnet; GET leitet zur Stunde zurück (`77b0a62`) |
| `/dev/stats/` ohne Daten, Middleware nie eingehängt | Bewusst aktiviert — mit Löschfrist von 30 Tagen, pseudonymer Sitzungskennung und einem Abschnitt in der Datenschutzerklärung (`2ab9197`) |
| Doppelte `PII_KEYS`/`PHONE_PATTERN` in `apps/ai/utils_safety.py` | Je eine Definition entfernt, samt des Kommentars, der die Entfernung schon behauptet hatte (`77b0a62`) |
| Keine `.gitignore` im Projektstamm | **Offen, bewusst.** `scripts/repo_hygiene_check.sh` verbietet eine versionierte Stamm-`.gitignore` ausdrücklich und bricht den Commit ab. Der Einwand des Reviews bleibt gültig: Ein frischer Klon ohne `setup_local_git.sh` hat bis zum Push keinen Schutz, und bei einem öffentlichen Repository kommt die CI-Prüfung zu spät. Eine Änderung dieser Regel ist eine Entscheidung von Andreas |

## Nicht aus dem Review, im selben Zug erledigt

| Thema | Umsetzung |
|-------|-----------|
| Rate-Limit antwortete mit 403 samt Traceback | Eigene Antwort mit Status 429 und `Retry-After` (`5c2a6d2`) |
| Logs liefen über (jede Meldung doppelt, 404 als Warnung) | Doppelte Weitergabe abgeschaltet, 404 herausgefiltert (`db6acb9`) |
| Portal-Login für Schüler und Eltern nicht auffindbar | Verweis auf der Start- und der Login-Seite (`5f76ba2`) |

# Externer Code-Review 22.09.2026 — Befunde und Umsetzung

**Quelle:** Code-Review von außen (Datei `preceptly-codereview-2026-09-22.md`)
**Bearbeitet:** 22.–23.09.2026
**Stand:** 10 von 10 Befunden und alle P3-Punkte erledigt.
Offen bleibt nur das Scharfschalten der Content-Security-Policy.

## P1 — zeitnah beheben

| # | Befund | Umsetzung |
|---|--------|-----------|
| 1 | Meeting-Raum lädt pdf.js 3.11.174 vom CDN, betroffen von CVE-2024-4367; Eltern können PDFs hochladen, die der Tutor im Raum öffnet | `isEvalSupported: false` an beiden `getDocument`-Aufrufen (`4d33de9`); pdf.js auf 6.3.289 gehoben und aus den eigenen Static-Files ausgeliefert statt vom CDN (`7561a8f`); CSP im Melde-Modus (`df696d7`) |
| 2 | Rate-Limits zählten pro Proxy statt pro Besucher — zehn Anfragen pro Minute konnten alle aussperren | `RATELIMIT_IP_META_KEY` nutzt jetzt dieselbe Client-IP-Ermittlung wie die Login-Drosselung (`4d33de9`). Live geprüft: 10 Versuche vom ai-server → 11. Versuch 429, gefälschter `X-Forwarded-For` wirkungslos, anderer Rechner unbetroffen |
| 3 | Dependabot-Aktualisierungen wurden vor den Tests zusammengeführt | Branch-Schutz mit Pflicht-Checks (`test`, `hygiene`); CI läuft jetzt auch bei Änderungen an `requirements*.txt` (`31ba176`); Dependabot nutzt `versioning-strategy: increase-if-necessary`, damit Untergrenzen korrekt als Patch/Minor erkannt werden (`4a5efc3`) |

## P2 — sinnvoll, nicht dringend

| # | Befund | Umsetzung |
|---|--------|-----------|
| 4 | Keine Content-Security-Policy | Richtlinie im Melde-Modus aktiv (`df696d7`), siehe `docs/operations/content-security-policy.md`. **Scharfschalten steht noch aus** — erst die Meldungen auswerten |
| 5 | Portal-Login ohne Drosselung pro Konto | Zusätzliche Drosselung pro E-Mail-Adresse, fünf Versuche in fünf Minuten (`6c9013c`) |
| 6 | L4 aus dem Juli-Audit nur teilweise behoben | `apps/portal/identity.py` prüft beide Anmeldewege — Django-User **und** Vertrags-E-Mail eines `StudentPortalLink`; benutzt in Profiländerung und Einladung (`bd2b3b0`) |
| 7 | TURN-Zugangsdaten statisch und für jeden Teilnehmer sichtbar | Kurzlebige Zugangsdaten nach dem TURN-REST-Verfahren, 8 Stunden gültig (`393a7c2`); coturn am 23.09. auf `use-auth-secret` umgestellt und geprüft, siehe `docs/operations/turn-server.md` |
| 8 | Kalenderfeed: Token nicht erneuerbar, Notizen landen in fremden Kalendern | Feed-Link erneuerbar, Notizfeld ehrlich beschriftet (`d43cee5`) |
| 9 | Dokumentation hinkt dem Code hinterher | Vollständige Liste der Umgebungsvariablen (`02b679e`), neue Betriebsdoku zu TURN und CSP, Doku-Index ergänzt (`dd26979`), dieser Bericht |
| 10 | Doppelte Dekoratoren an der öffentlichen Buchung | Entfernt, dazu ein doppeltes `@csrf_exempt` am Stripe-Webhook (`4d33de9`) |

## P3 — Aufräumen

| Punkt | Umsetzung |
|-------|-----------|
| `StartMeetingView` ändert per GET den Zustand | Raum wird nur noch per POST aus einem CSRF-geschützten Formular geöffnet; GET leitet zur Stunde zurück (`fe4d955`) |
| `/dev/stats/` ohne Daten, Middleware nie eingehängt | Bewusst aktiviert — mit Löschfrist von 30 Tagen, pseudonymer Sitzungskennung und einem Abschnitt in der Datenschutzerklärung (`162e924`) |
| Doppelte `PII_KEYS`/`PHONE_PATTERN` in `apps/ai/utils_safety.py` | Je eine Definition entfernt, samt des Kommentars, der die Entfernung schon behauptet hatte (`fe4d955`) |
| Keine `.gitignore` im Projektstamm | Regel auf Wunsch von Andreas gelockert: Der Hygiene-Check verbietet die Datei nicht mehr, stattdessen ist sie angelegt (`496b915`). Sie wirkt ab dem Klonen; `repo_hygiene_check.sh` bleibt als zweite Linie und greift auch bei erzwungenem `git add -f` |

## Nicht aus dem Review, im selben Zug erledigt

| Thema | Umsetzung |
|-------|-----------|
| Rate-Limit antwortete mit 403 samt Traceback | Eigene Antwort mit Status 429 und `Retry-After` (`f6519c8`) |
| Logs liefen über (jede Meldung doppelt, 404 als Warnung) | Doppelte Weitergabe abgeschaltet, 404 herausgefiltert (`1761ee9`) |
| Portal-Login für Schüler und Eltern nicht auffindbar | Verweis auf der Start- und der Login-Seite (`764eff9`) |

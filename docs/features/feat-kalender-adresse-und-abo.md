# Kalender per Adresse (Google) und Kalender-Abo für Tutoren

**Stand:** 16.11.2026 · Auftrag von Andreas (10.11.2026, auf die Frage „Kann man auch Google- und iCloud-Kalender
verbinden?“): „Ja, mach das so.“

## Überblick

Bis dahin ließ sich nur ein **iCloud**-Kalender verbinden (CalDAV, mit App-Passwort), und die Karte war nur auf Mac,
iPhone und iPad sichtbar. Google verlangt für CalDAV OAuth 2.0 (Basic-Auth wird mit 401 abgelehnt); das hieße
App-Prüfung durch Google und Token-Verwaltung. Stattdessen drei kleine, nur lesende Wege ohne Passwort:

| Teil | Richtung | Mittel | Ergebnis |
|---|---|---|---|
| (a) Sichtbarkeit | – | Karte „Kalender“ in den Einstellungen | auf **allen** Geräten sichtbar |
| (b) Kalender per Adresse | Google → Preceptly | „Geheime Adresse im iCal-Format“ | Termine werden **Blockzeiten** |
| (c) Kalender-Abo | Preceptly → Google, iCloud, Outlook | geheimer Abo-Link (iCal-Feed) | Stunden erscheinen im Kalender des Tutors |

Beides nur lesend: In Google wird nie etwas geschrieben, und Änderungen im Kalender-Programm ändern keine Stunde in Preceptly.

## (b) Kalender per Adresse

**Für den Tutor:** Einstellungen → Kalender → „Kalender per Adresse (Google)“. Die geheime Adresse steht in Google Kalender unter
Einstellungen → Kalender → „Kalender integrieren“ → „Geheime Adresse im iCal-Format“. Bis zu **5** Adressen je Tutor.

**Ablauf:** Beim Hinzufügen wird die Adresse sofort abgerufen und geprüft. Nur was sich lesen lässt, wird gespeichert; sonst
erscheint eine Meldung, und es entsteht nichts. Danach gleicht der Cron (`sync_calendars`, alle 5 Minuten) jede Quelle **höchstens
alle 15 Minuten** ab (nach einem Fehler höchstens stündlich). „Jetzt abgleichen“ gibt es zusätzlich, höchstens einmal pro Minute.

**Regeln des Abgleichs** (`apps/calendar_sync/ics_sync.py`):

- Zeitraum **7 Tage zurück, 180 Tage voraus** (wie beim iCloud-Abgleich). Wiederholungen werden je Tag aufgelöst, auch Ausnahmen
  und verschobene Einzeltermine.
- Übernommen wird **nur der Titel** (keine Beschreibung, Teilnehmer, Orte). Ganztägige Termine blockieren von 0 bis 24 Uhr
  Ortszeit (Europe/Berlin, wenn der Kalender keine Zeitzone nennt).
- **Nicht übernommen:** abgesagte Termine, als „verfügbar“ markierte (Geburtstage, Erinnerungen), Termine ohne Dauer und
  **eigene Stunden** (Kennung endet auf `@preceptly.de`), damit sich Preceptly nicht selbst blockiert.
- Neu → Blockzeit. Titel geändert → Blockzeit wird angepasst. Aus dem Kalender verschwunden (im Zeitraum) → Blockzeit wird gelöscht.
  Verschiebt sich ein Termin, gilt das als neuer Termin (der Beginn gehört zur Kennung).
- **Löscht der Tutor** eine importierte Blockzeit selbst, kommt sie nicht wieder, solange der Termin im Kalender steht
  (`IcsEventMapping.blocked_time = NULL` als Merkzettel).
- **Fehler ändern nichts:** Schlägt Abruf oder Auswertung fehl, bleiben alle Blockzeiten vom letzten guten Lauf stehen; an der
  Quelle steht nur ein Fehlercode, der in der Oberfläche als Satz erscheint.
- **Quelle entfernen** löscht auch die daraus importierten Blockzeiten (sonst blieben unlöschbare Altlasten). Von Hand
  angelegte Blockzeiten bleiben immer.
- **Tarif:** Wie beim iCloud-Import gilt keine Tarifgrenze: Der Import spiegelt nur, was im Kalender steht (siehe PRD, Ausnahme
  iCloud-Sync).

### Sicherheit

Die Adresse ist wie ein Passwort: Wer sie kennt, kann den ganzen Kalender lesen.

- **Verschlüsselt gespeichert** (derselbe Fernet-Schlüssel `CALDAV_ENCRYPTION_KEY` wie das iCloud-Passwort). Ein SHA-256-Wert
  erkennt Doppelte, ohne zu entschlüsseln. Sie wird **nie** wieder angezeigt (nur Name und Rechner), nie in Meldungen,
  Weiterleitungen, Admin oder Protokollen genannt; das Eingabefeld ist verdeckt.
- **SSRF-Schutz** (der Server ruft eine Adresse ab, die ein Benutzer eingibt), `apps/calendar_sync/ics_import.py`: nur https,
  Port 443, keine Zugangsdaten in der Adresse, nur der Rechner `calendar.google.com` mit Pfad `/calendar/ical/`; der Name muss auf
  eine **öffentliche** Adresse zeigen; Weiterleitungen werden von Hand verfolgt (höchstens 3) und jedes Mal neu geprüft;
  5 MB, Zeitlimits (5 s Verbindung, 15 s Lesen); höchstens 5.000 Einträge und 3.000 Termine im Zeitraum.
- **Bekannte Restlücke:** DNS-Rebinding (der Name wird für die Prüfung und beim Abruf getrennt aufgelöst). Das Risiko ist klein,
  solange nur `calendar.google.com` erlaubt ist. Wer die Erlaubnisliste (`ALLOWED_SOURCES`) um Rechner erweitert, die Dritte
  kontrollieren können, muss den Abruf an die geprüfte IP binden.
- Rate-Limit: Hinzufügen 10/Stunde, „Jetzt abgleichen“ 30/Stunde je Konto.

## (c) Kalender-Abo

Einstellungen → Kalender → „Kalender-Abo“ → einschalten. Es entsteht ein geheimer Link
(`/calendar-sync/feed/<Token>.ics`, auch als `webcal://`), den Google Kalender, Apple Kalender oder Outlook abonnieren.

- **Inhalt:** je Stunde (Status geplant, gehalten, bezahlt; nicht abgesagte) **nur Titel und Zeit**. Zeitraum 30 Tage zurück bis
  365 Tage voraus (wie der Portal-Feed). Zeiten in der Zeitzone des Tutors. **Keine** Notizen, Hausaufgaben, Meeting-Links,
  Orte, Teilnehmer.
- **Fahrzeiten sind nicht enthalten:** Das Abo zeigt die Unterrichtszeit, nicht die Blockzeit mit Anfahrt, die der iCloud-Abgleich schreibt.
- **Titel:** Standard **„Nachhilfe“ ohne Schülername**. Auf Wunsch „Nachhilfe - Vorname Nachname“. Begründung: Der Link ist für
  jeden lesbar, der ihn kennt, und der Kalenderdienst speichert die Titel im Konto des Tutors.
- **Link erneuern** macht den alten Link sofort ungültig; **ausschalten** löscht den Eintrag, der Link liefert danach 404.
- **Abruf:** öffentlich, ohne Login (der Token ist die Berechtigung, 122 Bit Zufall). Antwort mit `Cache-Control: private`,
  `X-Robots-Tag: noindex`, `Referrer-Policy: no-referrer`. Gesperrte Konten bekommen 404. Die Oberfläche zeigt, wann der Link zuletzt abgerufen wurde.
- **Hinweis in der Oberfläche:** Wer schon per iCloud-Abgleich schreibt und den Link in iCloud abonniert, sieht jede Stunde doppelt.
  Kalender-Programme aktualisieren Abos nach eigenem Takt; Änderungen können dauern.
- Der Token steht, wie die Adresse, nicht im Admin. Zugriffsprotokolle des Servers enthalten den Pfad mit dem Token (wie beim
  Portal-Feed); wer das Risiko ausschließen will, erneuert den Link.

## Datenschutz

Datenschutzerklärung (`privacy.html`, zwei neue Abschnitte) und AVV (neue Ziffer 6.3a) sind ergänzt. Google gilt wie Apple in 6.3
als Dienstleister des Tutors, nicht als Unterauftragsverarbeiter. Grundlage: Art. 6 Abs. 1 lit. b DSGVO. Belegt an Googles
eigenen Seiten (16.11.2026): Anbieter im EWR ist Google Ireland Limited (Gordon House, Barrow Street, Dublin 4); Google LLC ist
unter dem EU-US Data Privacy Framework zertifiziert und setzt Standardvertragsklauseln ein, wo nötig.

## Code

| Teil | Ort |
|---|---|
| Adresse prüfen, abrufen, Termine auswerten (ohne Django) | `apps/calendar_sync/ics_import.py` |
| Abgleich mit den Blockzeiten, Cron-Einstieg | `apps/calendar_sync/ics_sync.py` (`sync_all_ics_sources`, im Befehl `sync_calendars`) |
| Modelle | `models_ics.py` (`IcsCalendarSource`, `IcsEventMapping`), `models_feed.py` (`TutorCalendarFeed`) |
| Ansichten Adresse / Abo | `views_ics.py`, `views_feed.py` (Abruf: `tutor_feed`) |
| Abo-Datei | `feed.py` |
| Daten für die Einstellungsseite | `ui.py`, Vorlagen `templates/calendar_sync/_ics_card.html`, `_feed_card.html` |
| Tests | `test_ics_import.py`, `test_ics_sync.py`, `test_ics_views.py`, `test_tutor_feed.py` |
| Abhängigkeit | `recurring-ical-events==3.8.2` (löst Wiederholungen auf) |

## Nicht enthalten / offen

- **Nur Google.** Weitere Rechner (iCloud-Freigabelinks, Outlook) gehören in `ALLOWED_SOURCES`; vorher die Restlücke (DNS-Rebinding) schließen.
- **Kein Zurückschreiben** nach Google, kein OAuth.
- **Kein Löschen alter Blockzeiten** aus dem Kalender: Termine vor dem Zeitraum bleiben als Vergangenheit stehen.
- Der **CalDAV-Import (iCloud)** liest mit `expand=False`; wiederkehrende Termine kommen dort vermutlich nur einmal an
  (nicht geprüft, getrennt zu klären).

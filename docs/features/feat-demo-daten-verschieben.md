# Demo-Daten verschieben sich mit der Zeit

**Stand:** 20.11.2026 · Wunsch von Andreas: „Die Demo-Daten sollten sich mit der Zeit verschieben.“

## Ausgangslage

Die öffentlichen Demo-Konten (`demo_premium`, `demo_user`, Zugangsdaten stehen auf der Start- und der Login-Seite) waren zuletzt am
**23.06.2026** erzeugt worden. In der Produktion hatte `demo_premium` keine einzige Stunde ab heute, die Serie endete am 29.07., die
Blockzeiten im Juli, die Monatspläne gehörten zu November und Dezember 2025. Wer die Demo öffnete, sah ein leeres Dashboard. Das Konto
wird genutzt (letzter Login heute um 02:18 Uhr).

Zwei Ursachen:

1. **Feste Daten im Seed.** `seed_demo_data` rechnete die meisten Stunden vom heutigen Datum aus, hatte aber Vertragsbeginn,
   Monatspläne und die vier Quotenstunden mit festem Datum im Herbst 2025. Die Serien waren nur drei bzw. vier Wochen lang.
2. **Das „stündliche Zurücksetzen per Railway-Cron“ gab es nie.** So stand es im Kommentar von `demo_guard.py`. In Railway laufen nur die
   App, Redis und Postgres, `railway.json` enthält keinen Cron. Der Seed lief einmal von Hand und nie wieder.

## Lösung

**Der Seed rechnet alles vom heutigen deutschen Datum aus** (`timezone.localdate()`):

| Was | vorher | jetzt |
|---|---|---|
| Vertragsbeginn | 01.11.2025 usw. | 1 bis 3 Monate vor heute |
| Monatspläne | November und Dezember 2025 | laufender und nächster Monat |
| Quotenkonflikt (4 Stunden bei 3 geplanten) | 5., 12., 19., 26.11.2025 | 3., 10., 17., 24. des **nächsten** Monats (immer in der Zukunft) |
| Serien | 4 und 3 Wochen | 8 und 7 Wochen (eine ausgefallene Auffrischung leert die Demo nicht sofort) |
| Stunden, Blockzeiten, Rechnungen | heute ± n Tage | unverändert relativ |

**Die Daten werden einmal je Kalendertag neu erzeugt** (`apps/core/demo_refresh.py`), beim ersten Zugriff eines Demo-Kontos an diesem
Tag. Das folgt dem Muster der Log-Bereinigung (`RequestLogMiddleware._maybe_purge`): Sperre im Cache, kein Zeitplaner, kein Cron.

- Schlüssel `demo_refresh:<Datum>` mit `cache.add`: Nur ein Zugriff frischt auf, die anderen laufen unberührt weiter. „Läuft gerade“ gilt
  5 Minuten (stirbt der Prozess, etwa bei einem Deploy, bleibt es nicht bis morgen hängen). Nach einem Fehler gibt es nach 10 Minuten einen
  neuen Versuch.
- **Nur Demo-Konten lösen es aus, und nur dort, wo es sie schon gibt.** Es wird nie eine Demo angelegt, wo keine ist (die Konten haben ein
  öffentliches Passwort).
- **Die Konten und ihre Profile bleiben** (`seed_demo_data --refresh`), sonst bräche ein laufender Login ab. Das Passwort wird auf `demo123`
  und die Tarifstufe auf Business (`demo_premium`) bzw. Free (`demo_user`) zurückgesetzt.
- **Eine Transaktion:** Schlägt das Neuerzeugen fehl, bleibt der alte Stand. Die Demo ist nie halb leer.
- **Besucher-Reste gehen mit:** Weil die Demo öffentlich ist, können Besucher mehr hinterlassen als Verträge: Kalenderverbindungen (iCloud),
  geheime Google-Adressen, Abo-Links, Push-Abos, Ausgaben und Portal-Konten. Das wird beim Auffrischen entfernt. Der Login-Nutzer hinter
  einem Portal-Konto bleibt bewusst bestehen: Eine Einladung kann ein echtes, schon bestehendes Konto getroffen haben.
- Änderungen, die Besucher in der Demo vornehmen, sind damit spätestens am nächsten Tag weg. Das war schon immer die Absicht (stündlich im
  alten Kommentar), nur nie umgesetzt.

Beim Deploy wird nichts automatisch geändert: Der erste Zugriff eines Demo-Kontos danach erzeugt die Daten neu.

## Geprüft

- `apps/core/tests/test_demo_refresh.py` (19 Tests) und die vorhandenen Seed-Tests. Der Seed läuft an sechs Tagen mit Sonderfällen
  (gewöhnlicher Tag, 31.12., 01.01., Schaltjahr 29.02.2028, Monatsende 31.03., Monatsanfang): nichts liegt weit weg vom Erzeugungstag, jedes
  Demo-Konto hat in der nächsten Woche Stunden, der Quotenkonflikt bleibt einer. Auffrischen: Konten und Profile bleiben, alte Verträge sind
  ersetzt, Besucher-Reste und zurückgesetzte Passwörter, fremde Konten bleiben unberührt, einmal je Tag, nur für Demo-Konten, Fehler ändern
  nichts und erlauben einen neuen Versuch, es entsteht nie eine Demo, wo keine ist, und die Middleware frischt beim ersten Zugriff auf.
- **Mutationstest:** 15 Fehler gezielt eingebaut (feste Daten zurück im Vertragsbeginn, bei den Quotenstunden und bei den Serien; Auffrischen löscht die Konten; Kalenderadresse, Abo-Adresse, Push-Abos und Portal-Konten bleiben liegen; Tarifstufe und Passwort werden nicht zurückgesetzt; Tagessperre fehlt; jeder Nutzer löst es aus; keine Transaktion; ein Fehler sperrt bis morgen; Middleware nicht verdrahtet). Alle 15 werden von den Tests bemerkt. Davor fielen zwei Lücken auf und wurden geschlossen: Die Besucher-Reste (Kalender, Push, Portal) und die Tarifstufe waren nicht abgesichert.

## Nachtrag 20.11.2026: Funde bei dieser Arbeit, behoben

- **Portal-Einladungen aus der Demo.** `PortalInviteView`, Erneut-Senden und Login-Erinnerung hatten weder eine Sperre für Demo-Konten noch
  ein Ratelimit: Mit den öffentlichen Zugangsdaten konnte jeder Besucher Einladungs-E-Mails an beliebige Adressen von der Preceptly-Domain
  auslösen. Jetzt sperrt `demo_block` alle drei.
- **Kalender aus der Demo.** Die iCloud-Anbindung und das Eintragen einer geheimen Google-Adresse sind für Demo-Konten gesperrt: Ein
  Besucher konnte seinen echten Kalender in einem Konto ablegen, dessen Termine alle sehen, die sich mit den öffentlichen Zugangsdaten
  anmelden (die tägliche Auffrischung begrenzte das nur auf einen Tag). Abo-Link und Abgleich bleiben möglich, sie enthalten keine Geheimnisse
  eines Besuchers.
- **Totes Modell `RecurringBlockedTime`.** Die Tabelle ist seit Migration 0008 weg, die Klasse blieb als Modell mit Fremdschlüssel auf den
  Nutzer und wird in `BlockedTimeCreateView.form_valid` bei jedem Anlegen einer Blockzeit importiert. Danach scheiterte im selben Prozess jedes
  `User.delete()` ("no such table"), in der Produktion zum Beispiel beim Löschen eines Schülers mit Portal-Konto, bis zum nächsten Neustart. Jetzt
  ist die Klasse ein reiner Datenhalter (`dataclass`) ohne Tabelle und ohne Beziehung zum Nutzer; die tote Funktion
  `find_matching_recurring_blocked_time` (fragte die gelöschte Tabelle ab, ohne Aufrufer) ist entfernt. `makemigrations --check` meldet keine
  Änderung.
- Geprüft mit neun eingebauten Fehlern (Sperre je Ansicht entfernt, Sperre trifft jeden, Datenhalter wieder ein Modell, Wochentage und
  inaktive Serie falsch): alle neun werden bemerkt. Tests: `apps/core/tests/test_demo_outbound_guard.py` (mit Gegenprobe für normale Tutoren),
  `apps/blocked_times/test_recurring_holder.py`.
- Unverändert: Die Demo-Konten haben `is_staff=True` (ohne Superuser und Berechtigungen, öffnet nur ein leeres Admin-Fenster; die
  Statistikseite hat einen eigenen Passwortschutz). `--clear` löscht weiterhin die Konten selbst.

## Code

| Teil | Ort |
|---|---|
| Seed, `--refresh`, zeitrelative Daten | `apps/core/management/commands/seed_demo_data.py` |
| Tagessperre, Auffrischung, Middleware | `apps/core/demo_refresh.py` (eingebunden in `settings.MIDDLEWARE`) |
| Beschreibung des Missbrauchsschutzes | `apps/core/demo_guard.py` |
| Tests | `apps/core/tests/test_demo_refresh.py` |

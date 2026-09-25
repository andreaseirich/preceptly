# Datensicherung (Backup)

**Stand:** 25.09.2026 — eingerichtet, erster Lauf wiederhergestellt und geprüft.

Der AVV sagt Tutoren tägliche Datensicherungen zu (Abschnitt 5, TOMs). Bis
25.09.2026 gab es keine automatische Sicherung; `manage.py backup_db` schreibt
ins Dateisystem des Containers und hilft auf Railway nicht.

## Überblick

| | |
|---|---|
| Inhalt | Datenbank (vollständiger `pg_dump` als SQL, gzip) und hochgeladene Dokumente (`/app/backend/media`, tar.gz) |
| Zeitpunkt | täglich 03:15 UTC |
| Ziel | Backup-Server bei Hetzner in Deutschland — als Unterauftragsverarbeiter im AVV und in der Datenschutzerklärung genannt |
| Verschlüsselung | GPG mit dem öffentlichen Schlüssel, direkt beim Eintreffen; der private Schlüssel liegt **nicht** auf dem Backup-Server |
| Aufbewahrung | 30 Tage, danach automatisch gelöscht (so auch in der Datenschutzerklärung zugesagt) |
| Warnung | Push-Nachricht an den Betreiber, wenn ein Lauf scheitert oder der Dump verdächtig klein ist |

## Ablauf

1. Der Backup-Server startet per `railway ssh` im Produktiv-Container `pg_dump`.
   Dort liegt pg_dump 17 passend zum Datenbankserver — ein Dump von außen
   bräuchte dieselbe Hauptversion und eine öffentlich erreichbare Datenbank.
2. Der Dump wird im Container zuerst vollständig in eine temporäre Datei
   geschrieben und auf die Schlusszeile `PostgreSQL database dump complete`
   geprüft. Ein abgebrochener Dump kommt gar nicht erst heraus.
3. Komprimiert kommt er über stdout und wird beim Eintreffen verschlüsselt.
   Klartext liegt auf dem Backup-Server nie auf der Platte.
4. Dasselbe für die Dokumente als tar.gz.

Es braucht keine eigenen Zugangsdaten zur Datenbank: Der Weg nutzt denselben
`railway ssh`-Zugang wie die Kalender-Synchronisierung.

## Warum der Schlüssel woanders liegt

Der Backup-Server betreibt viele Dienste. Er kann Backups schreiben, aber nicht
lesen — wer ihn übernimmt, kommt trotzdem nicht an Schülerdaten aus den
Sicherungen. Der private Schlüssel liegt beim Betreiber, mit einer zweiten Kopie
im Passwort-Manager. **Gehen beide verloren, sind alle Backups wertlos.**

## Wiederherstellen

Pfade, Schlüssel-Fingerprint und fertige Befehle stehen in den privaten
Betriebsunterlagen, nicht in diesem öffentlichen Repo. Grundsätzlich:

1. Backup vom Backup-Server holen, mit dem privaten Schlüssel entschlüsseln
   (`gpg --decrypt`), dann `gunzip`.
2. In eine **leere** Postgres-17-Datenbank einspielen:
   `psql "$ZIEL_URL" -v ON_ERROR_STOP=1 -f preceptly.sql`.
   Dumps ab Postgres 17.6 enthalten `\restrict`-Zeilen — dafür braucht es psql
   17.6 oder neuer.
3. Dokumente: entschlüsseln und mit `tar -xzf - -C <media-Verzeichnis>` auspacken.

Beim Holen der Datei eine eigene SSH-Verbindung nutzen
(`-o ControlMaster=no -o ControlPath=none`): Über eine gemultiplexte Verbindung
kam einmal ein abgeschnittener Datenstrom an. gpg meldet das als
Prüfsummenfehler — die Datei auf dem Backup-Server war dabei heil.

## Prüfung am 25.09.2026

- **Datenbank:** auf dem Rechner mit dem privaten Schlüssel entschlüsselt, Zeilen
  pro Tabelle aus den `COPY`-Blöcken gezählt und mit der Live-Datenbank
  verglichen: 39 von 39 Tabellen, 4.284 von 4.284 Zeilen.
- **Dokumente:** entschlüsselt, 5 Dateien mit 11.619.255 Bytes — identisch mit
  dem Container.
- **Offen:** Einspielen in einen echten Postgres-17-Server. Beim Test war keiner
  verfügbar; die Prüfung oben zeigt, dass alle Daten vollständig und lesbar im
  Backup stecken, aber nicht, dass `psql` sie fehlerfrei lädt.

## Bekannte Grenzen

- Läuft der Cron-Job gar nicht (Server aus, Crontab verloren), kommt keine
  Warnung — nur ein gescheiterter Lauf meldet sich.
- Ein Backup pro Tag: Im schlimmsten Fall gehen die Änderungen seit 03:15 UTC
  verloren.

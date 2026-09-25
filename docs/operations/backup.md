# Datensicherung (Backup)

**Stand:** 25.09.2026

## Railway-Snapshots

Railway sichert alle Volumes des Projekts selbst — Datenbank, hochgeladene
Dokumente und Redis.

| | |
|---|---|
| Häufigkeit | täglich (Zeitplan je Volume im Railway-Dashboard) |
| Aufbewahrung | 6 Tage; vor Sicherheitspatches legt Railway zusätzlich einen Stand an, der 30 Tage bleibt |
| Ort | bei Railway, also beim selben Anbieter wie die Produktion |
| Wiederherstellen | Railway-Dashboard → Dienst → Backups → Stand wählen |

Beim Wiederherstellen legt Railway ein neues Volume an und hängt das alte ab.
So entstand am 31.01.2026 das Volume `postgres-volume`, das seitdem an keinem
Dienst mehr hängt.

Die `railway`-CLI zeigt die Snapshots nicht an, nur das Dashboard oder die
GraphQL-API (`volumeInstanceBackupList`). Wer prüfen will, ob es Backups gibt,
muss dort nachsehen.

Manuelle Backups im Dashboard laufen nur ab, wenn man ein Ablaufdatum setzt.
Sonst bleiben sie mit allen Personendaten liegen, bis jemand sie löscht.

`manage.py backup_db` schreibt ins Dateisystem des Containers und ist für
Railway nicht gedacht.

## Grenzen

Die Snapshots liegen beim selben Anbieter. Sie helfen nicht, wenn das
Railway-Konto oder -Projekt verloren geht, und nicht bei Fehlern, die erst nach
mehr als 6 Tagen auffallen.

## Entscheidung 25.09.2026: kein eigenes Backup außerhalb von Railway

Am 25.09.2026 lief für einige Stunden ein zusätzliches eigenes Backup: täglich
`pg_dump` und Dokumente per `railway ssh`, GPG-verschlüsselt, 30 Tage auf einem
Server bei Hetzner in Deutschland. Dafür stand Hetzner als
Unterauftragsverarbeiter in AVV und Datenschutzerklärung. Der erste Lauf war
wiederhergestellt und geprüft.

Andreas hat es am selben Tag zurücknehmen lassen. AVV und Datenschutzerklärung
sind wieder auf dem Stand vom 19.09.2026. Aufbau und Prüfung stehen in Commit
`a059799` (`docs/operations/backup.md`), falls es später doch kommen soll.

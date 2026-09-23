# TURN-Server (coturn)

**Stand:** 23.09.2026

Video-Meetings laufen direkt zwischen den Browsern (WebRTC). Wenn beide Seiten
hinter NAT oder einer Firewall sitzen, kommt keine direkte Verbindung zustande —
dann läuft der Ton- und Videostrom über den TURN-Server.

## Wo läuft er

| | |
|---|---|
| Host | ai-server, `46.224.151.16` |
| Dienst | `coturn` (`systemctl status coturn`) |
| Konfiguration | `/etc/turnserver.conf` |
| Ports | 3478 UDP und TCP, Relay-Bereich 49152–65535 |
| Realm | `preceptly.turn` |
| Log | `/var/log/coturn.log` |

## Anmeldung: kurzlebige Zugangsdaten

Bis zum 23.09.2026 stand in der Konfiguration ein fester Benutzer
(`user=preceptly:…`). Dessen Passwort wurde im Quelltext jeder Meeting-Seite
ausgeliefert und war unbegrenzt gültig — wer es einmal ablas, konnte den
Relay-Server dauerhaft mitbenutzen.

Seitdem gilt das Verfahren „TURN REST API" (coturn: `use-auth-secret`):

```
Benutzername = "<Unix-Zeit des Ablaufs>:<Zufallskennung>"
Passwort     = base64(HMAC-SHA1(Benutzername, gemeinsames Geheimnis))
```

Die Anwendung erzeugt diese Daten für jede Meeting-Seite neu
(`backend/apps/meeting/turn_auth.py`); sie verfallen nach
`TURN_CREDENTIAL_TTL_SECONDS` (Standard: 8 Stunden).

Das gemeinsame Geheimnis liegt an drei Stellen und muss überall identisch sein:

| Ort | Wert |
|---|---|
| coturn | `static-auth-secret=` in `/etc/turnserver.conf` |
| Anwendung | Railway-Variable `TURN_STATIC_AUTH_SECRET` |
| Sicherung | `/root/.turn_secret` auf dem ai-server (nur root lesbar) |

`TURN_CREDENTIAL` ist die alte, feste Variante. Sie wird nur noch benutzt, wenn
`TURN_STATIC_AUTH_SECRET` fehlt — auf dem Server gibt es den dazugehörigen
Benutzer aber nicht mehr, die Variable ist also wirkungslos und bleibt nur als
Rückfallebene für eine Rückabwicklung stehen.

## Geheimnis wechseln

1. Neues Geheimnis erzeugen: `openssl rand -hex 32 | sudo tee /root/.turn_secret`
2. Railway: `railway variables --service preceptly --set "TURN_STATIC_AUTH_SECRET=<neu>"`
3. Warten, bis die neue Version online ist (`railway status`).
4. coturn: `static-auth-secret=` in `/etc/turnserver.conf` ersetzen, dann
   `sudo systemctl restart coturn`.

Zwischen Schritt 3 und 4 liegt ein kurzes Fenster, in dem der Relay nicht
funktioniert. Direktverbindungen (der Normalfall) sind davon nicht betroffen.

## Prüfen, ob es funktioniert

```bash
SECRET=$(sudo cat /root/.turn_secret)
read -r U P < <(S="$SECRET" python3 -c "
import base64, hashlib, hmac, os, time
s = os.environ['S']
u = f'{int(time.time()) + 3600}:pruefung'
print(u, base64.b64encode(hmac.new(s.encode(), u.encode(), hashlib.sha1).digest()).decode())
")
turnutils_uclient -u "$U" -w "$P" -n 2 -c -y 46.224.151.16
```

Erwartete Ausgabe: Die Zuteilung („Allocation") gelingt, danach meldet der Test
`channel bind: error 403 (Forbidden IP)`. Das 403 ist **kein Fehler der
Anmeldung**, sondern Absicht: Der Testclient will den Datenstrom an eine private
Adresse weiterleiten, und private Netze sind in der Konfiguration gesperrt
(`denied-peer-ip`). Wer bis zum Channel-Bind kommt, war erfolgreich angemeldet.

Zum Gegentest mit einem falschen Passwort erscheint stattdessen
`ERROR: Cannot complete Allocation`.

## Rückabwicklung

Sicherung der alten Konfiguration: `/etc/turnserver.conf.bak-2026-09-23`.
Wiederherstellen, `sudo systemctl restart coturn`, und in Railway
`TURN_STATIC_AUTH_SECRET` löschen — danach liefert die Anwendung wieder das
feste Passwort aus.

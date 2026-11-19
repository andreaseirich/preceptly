# Datenschutz: Abgleich der Erklärung mit dem System

**Stand:** 19.11.2026 · Frage von Andreas: „Ist die Datenschutzerklärung aktuell?“ Geprüft wurden die Erklärung, der AVV und die
live ausgelieferte Seite gegen Code, Produktionsumgebung (nur lesend) und Server. Das ist ein technischer Abgleich, keine
Rechtsberatung.

## Befunde und Maßnahmen

| # | Befund | Maßnahme |
|---|---|---|
| 1 | Das Meeting nutzte neben dem eigenen TURN-Server (Hetzner) **auch die STUN-Server von Google**. Die Erklärung nannte nur Google, nicht den eigenen Relay-Server. Der AVV nannte Hetzner nicht (am 17.11. mit dem Backup entfernt, der TURN-Server blieb bei Hetzner) | Google-STUN abgeschaltet: Der Verbindungsaufbau nutzt den eigenen coturn-Server (`STUN_URL`, Standard `stun:46.224.151.16:3478`). Erklärung: neuer Absatz zum Relay (Hetzner, Zugangsdaten höchstens 8 Stunden, kein Zugriff auf Inhalte). AVV: Hetzner in der Tabelle, neuer Absatz 6.2a |
| 2 | Browser-Speicher unvollständig: Das Sprach-Cookie `django_language` (Sitzungs-Cookie, nur nach Umstellen der Sprache) und die Merkzettel für den Entwicklungshinweis (localStorage/sessionStorage) fehlten | in der Erklärung ergänzt |
| 3 | „Letzte Aktualisierung“ stand auf 19.09.2026, obwohl am 17.11. Abschnitte dazukamen | Datum in Erklärung, AVV und `LEGAL_LAST_UPDATED` auf 19.11.2026, mit dem Nachtrag (30-Tage-Frist) auf 20.11.2026 fortgeschrieben |
| 4 | Chat und Whiteboard laufen durch den Anwendungsserver, die Diagnosemeldungen stehen in den Railway-Logs; beides fehlte | ergänzt (Chat und Whiteboard werden nicht gespeichert) |
| 5 | Der von eRecht24 erzeugte Cloudflare-Abschnitt beschrieb ein CDN, das den Datenverkehr durchleitet. Tatsächlich ist Cloudflare nur DNS (Nameserver); die Antworten kommen direkt von Railway (`server: railway-hikari`, kein `cf-ray`, A-Eintrag bei Railway) | Abschnitt und Gruppenüberschrift beim Ausliefern ersetzt, siehe unten |
| 6 | Das eRecht24-Skript wird auf jeder Seite des Kerns geladen (Footer), im Portal nicht. Beim Seitenaufruf geht die IP an eRecht24, unabhängig vom Gebrauch des Buttons | Absatz im Preceptly-Teil |

## Geprüft und in Ordnung

- **Zugriffsprotokolle:** Die Felder entsprechen dem Text (Pfad, Methode, Status, Dauer, IP, Browser, Referrer, Sitzungskennung, Konto).
  Die Löschung nach 30 Tagen wirkt: 47.353 Einträge, der älteste genau 30 Tage alt, keiner älter als 31 Tage.
- **KI:** `LLM_MODEL_NAME=qwen2.5:7b`, `LLM_API_BASE_URL` auf den Tailscale-Rechner, kein externer Anbieter.
- **E-Mail:** `EMAIL_HOST=smtp.mail.me.com` (iCloud). Kalender (iCloud, Google-Adresse, Abo-Link), Push, Stripe (im erzeugten Teil)
  und „kein Tracking“ stimmen. Als externer Host kommt nur der eRecht24-CDN vor.
- **Bark-Meldungen** (Fehlerhinweise aufs Handy) enthalten nur Datei, Zeile und Fehlerart, nie Meldungstexte; der Server ist eigen
  (`bark.andicode.de`). Kein Eintrag nötig.

## Anpassung des erzeugten Textes (`apps/core/legal_overrides.py`)

eRecht24 erzeugt den allgemeinen Teil aus Bausteinen (per Webhook, 24 Stunden im Zwischenspeicher) und kennt nicht jede Einrichtung.
`apply_privacy_overrides()` ersetzt beim Ausliefern den Cloudflare-Baustein (`<h3>Cloudflare</h3>` bis zur nächsten Überschrift) und
benennt die Gruppenüberschrift „2. Hosting und Content Delivery Networks (CDN)“ in „2. Hosting und DNS“ um, jeweils deutsch und
englisch. Sicherheitsnetz: Findet sich eine Überschrift nicht genau einmal (eRecht24 hat sie umbenannt), bleibt der erzeugte Text
unverändert und es gibt eine Warnung im Log. Die Seite fällt nie aus. Am echten Text der Live-Seite geprüft: Es ändern sich nur diese
beiden Stellen, die Nachbarabschnitte bleiben gleich, und im übrigen Text bleibt keine CDN-Aussage übrig.

**Zu beachten:** Streicht eRecht24 den Cloudflare-Baustein ganz, entfällt auch unser Ersatz (und damit jede Erwähnung des DNS-Dienstes
in der Erklärung). Dann gehört der Abschnitt in den Preceptly-Teil (`privacy.html`). Die Warnung im Log weist darauf hin.

## Geprüft (Tests)

- `apps/core/tests/test_legal_overrides.py`: Ersetzen bis zur nächsten Überschrift, Nachbarn unberührt, letzter Abschnitt, umbenannte oder
  doppelte Überschrift (nichts geändert, Warnung), Sonderzeichen in der Überschrift, beide Sprachen, die Seite selbst.
- `apps/core/tests/test_privacy_statements.py`: bindet Text und Verhalten aneinander. Kein ICE-Server eines Dritten, STUN und TURN auf
  demselben Host, Hetzner in Erklärung und AVV, kein `stun.l.google.com` mehr, das Sprach-Cookie wird wirklich gesetzt und endet mit der
  Sitzung, Datum der Seiten stimmt mit `LEGAL_LAST_UPDATED` überein.
- **Mutationstest:** Acht Fehler gezielt eingebaut (Google-STUN wieder in der Liste, Abschnitt bis zum Ende ersetzt, doppelte Überschrift ungeschützt, Sprach-Cookie fehlt im Text, Hetzner fehlt im AVV, Ansicht wendet die Anpassung nicht an, Datum im Preceptly-Teil veraltet, Gruppenüberschrift bleibt CDN). Alle acht werden bemerkt. Im ersten Durchlauf überlebte das veraltete Datum: Der Test fand das Datum auch im Seitenkopf. Er prüft jetzt gezielt den Preceptly-Teil.

## Erledigt nach Rückfrage (19.11.2026)

1. **AVV mit Hetzner:** Andreas hat bestätigt, dass der Vertrag über Auftragsverarbeitung im Hetzner-Konto abgeschlossen ist.
2. **Aufbewahrung des coturn-Journals:** `journald` auf dem ai-server ist auf 30 Tage begrenzt (`MaxRetentionSec=30day`,
   `MaxFileSec=1day` in `/etc/systemd/journald.conf.d/30-retention.conf`). Beim Neustart von journald fielen alle Dateien über 30 Tage
   weg (Einträge ab April 2026, vorher keine Grenze), dazu eine Altdatei von 25.01.2026 in einem Verzeichnis einer früheren
   Maschinenkennung. Das Journal hat jetzt Einträge ab 22.10.2026 (473 MB). Die Erklärung nennt die 30 Tage; ein Test bindet den Text.

## Offen

- **eRecht24-Generator:** Cloudflare dort als „nur DNS“ führen, falls das möglich ist, dann entfällt unsere Anpassung.
- Die 30 Tage gelten für das **ganze** Journal des ai-server, nicht nur für coturn. Wer dort ältere Protokolle für eine Fehlersuche
  braucht, muss sie vorher sichern.

# Meeting-Raum: Verlassen, Medien ohne eigene Spuren, Whiteboard-Text

**Stand:** 29.10.2026 · Meldung von Andreas (mit drei Screenshots): „Man kann das Meeting nicht verlassen, man sieht und
hört sich gegenseitig nicht, trotz dass der Schüler schon drin war, und auch die Textfelder auf dem Whiteboard bleiben nicht auf
dem Whiteboard.“

## Befunde und Korrekturen

| # | Fehler | Ursache | Korrektur |
|---|---|---|---|
| 1 | Meeting lässt sich nicht verlassen | `hangUp` wartete mit `await fetch(END_URL)` auf die Antwort von „Meeting beenden“, bevor es die Seite wechselte. Hängt das Netz (die 5G-Verbindung wackelt, im Log mehrere Abbrüche), blieb die Seite für immer stehen. Mehrfaches Klicken schickte weitere Anfragen (drei 404 im Log um 18:30:24 bis :26) | Aufräumen ohne Netz (Peers, Kamera/Mikrofon aus, WebSocket zu), die Anfrage mit `keepalive` ohne Warten, nach höchstens 2 Sekunden geht es weiter. Ein Schutz (`_leaving`) lässt nur einen Durchlauf zu, die Knöpfe sind sofort gesperrt und zeigen „Verlasse das Meeting …“ |
| 2 | Kein Bild und Ton, obwohl „1 Teilnehmer verbunden“ | Ohne eigene Kamera-/Mikrofon-Spur enthält das WebRTC-Angebot **keinen Medienabschnitt**, man kann dann auch nichts **empfangen**. Der Beitretende erzeugt das Angebot. Verweigert sein Browser Kamera und Mikrofon (zum Beispiel nach dem Neuladen), steht die Verbindung nie (`new`), und es gibt auf **beiden** Seiten keine Kachel. Die Lobby lief dann mit leerem Strom weiter und zeigte „Mikrofon“ an, die Statuszeile zählte jeden Eintrag als „verbunden“ | `recvonly`-Abschnitte für fehlende Spuren (`addTransceiver`), damit man auch ohne eigene Geräte sieht und hört. Ehrliche Lobby (Meldung bei fehlendem Zugriff, Knöpfe „nicht verfügbar“, Ton allein/Bild allein als Rückfall). Kachel und Status je Teilnehmer sofort („Verbinde …“, „Verbindung fehlgeschlagen – neuer Versuch …“), ein ICE-Neustart auch bei `failed`. Statuszeile: „N Teilnehmer, M verbunden – Verbindung wird aufgebaut …“ |
| 3 | Whiteboard-Text verschwindet | Das Textfeld wurde nur beim Verlassen des Feldes (`blur`) bestätigt. Firefox und Safari geben Buttons auf dem Mac beim Klicken keinen Fokus, das Feld blieb offen und schwebte über allen Tabs (Screenshots: Whiteboard 01:05, Dokumente 01:14, Chat 01:23). Ein zweiter Klick aufs Whiteboard leerte das Feld, bevor es bestätigt war. Außerdem **ersetzte** der Abgleich beim Beitritt (`state_sync`) die eigene Zeichnung durch den Stand des anderen, ein Teilnehmer mit leerem Stand löschte so alles | Das Feld wird bestätigt bei Enter, bei jedem Klick oder Tipp außerhalb (Capture-Phase am Dokument), beim Tab-Wechsel, bei Größenänderung und beim Verlassen. Ein Leer-`blur` schließt ein frisch geöffnetes Feld nicht mehr. Der Abgleich beim Beitritt **ergänzt** nur (`mergeStrokes`), nichts geht verloren |

## Was geprüft wurde

Server und TURN waren **nicht** die Ursache: Es gibt nur eine Instanz (die Raumliste liegt im Prozess-Speicher, das ist dort in
Ordnung), und der TURN-Server (coturn, ai-server) akzeptierte mit den echten, kurzlebigen App-Zugangsdaten eine Relay-Zuweisung per
UDP und TCP; das gemeinsame Geheimnis stimmt überein.

Verhalten im Browser (Headless-Chrome, alte gegen neue Fassung, nicht Teil der CI):

- **Verlassen bei hängendem Netz:** alt bleibt stehen, neu wechselt nach 2 s. Bei intaktem Netz beide nach ca. 130 ms; bei drei
  Klicks schickte die alte Fassung drei Beenden-Anfragen, die neue eine.
- **Zwei Teilnehmer, echte WebRTC-Verbindung** (simulierter Signalisierungsserver): Wer ohne Kamera/Mikrofon beitritt (Schüler
  oder Tutor nach dem Neuladen), erzeugte alt eine Verbindung im Zustand `new` ohne Kachel auf beiden Seiten („1 Teilnehmer
  verbunden“, genau wie im Screenshot); neu steht die Verbindung, und wer Geräte hat, empfängt Bild und Ton.
- **Text-Werkzeug**, sieben Szenarien: Tab-Wechsel, zweiter Klick, Werkzeugleiste, Verlassen und Beitrittsabgleich verloren alt Text,
  neu bleibt er; Enter und Escape wie bisher.

Server (CI): `apps/meeting/test_room_robustness.py` (Logformat der Diagnose, Verhalten mit zwei Teilnehmern über
`WebsocketCommunicator`, und dass die Korrekturen in der ausgelieferten Seite stehen).

## Diagnose im Log

Neu schickt der Browser wenige kurze technische Meldungen (höchstens zwölf je Verbindung), der Server schreibt je eine Logzeile:

```
Meeting diag token=e8e108ff rolle=tutor peer=3f2a91c0 event=connected state=connected route=relay/host/udp local_audio=1 local_video=1 remote_tracks=2
```

- `event`: `join` (beim Beitritt, mit der Zahl eigener Spuren), `connected`, `failed`, `no_media_10s` (nach 10 s noch nichts von der
  Gegenseite).
- `route`: Art der ausgewählten Kandidaten (`host`, `srflx`, `relay`) und Protokoll. `relay` heißt: über TURN.
- Nur bekannte Felder, Zahlen 0 bis 99, Text auf wenige Zeichen begrenzt, kein Zeilenumbruch, nur ein Anfang des Raum-Tokens.
- Ansehen: `railway logs --service preceptly --filter "Meeting diag"`.

## Unverändert und offen

- Verlässt der **Tutor** das Meeting, wird es für alle beendet und der Raum-Token erneuert (`EndMeetingView`). Das ist Absicht.
- Bricht die Verbindung des Browsers zum Server ab, baut er sie neu auf (neue Peer-ID, die Medienverbindungen werden neu
  ausgehandelt). Bei einer instabilen Internetverbindung kommt es dadurch zu Unterbrechungen.
- **coturn schreibt kein Log:** `log-file=/var/log/coturn.log` ist konfiguriert, die Datei existiert nicht und journald ist
  leer, vermutlich darf der Dienst die Datei nicht anlegen. Für künftige Fehlersuche am TURN-Server sollte das behoben werden
  (Änderung auf dem ai-server, nicht im Repository).

## Code

| Teil | Ort |
|---|---|
| Verlassen, Diagnose, Verbindung, Kacheln, Lobby, Text-Werkzeug | `apps/meeting/templates/meeting/room.html` |
| Logzeile der Diagnose (`format_diag`, Zweig `diag`) | `apps/meeting/consumers.py` |
| Tests | `apps/meeting/test_room_robustness.py` |

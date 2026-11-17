# Meeting-Raum: Radierer und Rückkehr aus dem Hintergrund

**Stand:** 17.11.2026 · Meldung von Andreas nach einem Test mit dem Handy: Das Meeting läuft gut, mit zwei Ausnahmen. (1) „Das
Radiergummi radiert nicht die Zeichnungen, sondern malt mit hellgrau.“ (2) Wechselt man auf dem iPhone aus dem Browser in eine
andere App, geht die Verbindung verloren und kommt erst zurück, wenn der Browser wieder geöffnet wird. Sie solle bestehen bleiben,
und das Mikrofon solle weitersenden.

## Radierer

| Befund | Ursache | Korrektur |
|---|---|---|
| Der Radierer malt hellgrau, statt zu löschen | Das weiße Blatt (oder das PDF) und die Striche lagen auf **derselben** Zeichenfläche. Der Radierer löscht mit `destination-out`, das macht Pixel durchsichtig. Er stanzte also Löcher durch das Blatt, und darunter schien der graue Rahmen `#wb-canvas-wrap` (`#e8e8e8`) durch. Bei einem PDF im Hintergrund wäre auch das PDF weggeradiert worden | Die Striche entstehen auf einer **eigenen Ebene** (`wbLayer`) und werden danach auf das Blatt gelegt. Der Radierer wirkt nur dort. Beim Ziehen wird die Ebene je Bildschirmbild neu aufgebaut (`requestWbRedraw`), nach dem Loslassen einmal endgültig |
| Fremde Striche wurden ohne Zoom und Verschiebung gezeichnet | `handleWbEvent` rief `drawStroke` direkt auf, ohne die Ansichts-Transformation | Läuft jetzt über `redrawAll()`; damit wirkt auch ein radierender Strich der Gegenseite richtig |

Rückgängig (`undoWhiteboard`) stellt radierte Stellen wieder her, weil ein Radierstrich ein Eintrag in `wbStrokes` ist.

## Rückkehr aus dem Hintergrund

### Was eine Webseite nicht kann

Eine Webseite darf im Hintergrund **nicht weiterlaufen**. Auf dem iPhone hält iOS die Seite an, trennt Verbindungen und schaltet das
Mikrofon stumm, sobald man in eine andere App wechselt (so in öffentlichen WebKit-Fehlerberichten und Entwicklerforen beschrieben;
einen offiziellen Weg, das im Browser zu umgehen, gibt es dort nicht). Das lässt sich aus der Seite nicht abschalten. „Verbindung halten und Mikrofon weitersenden“ ist im Browser auf dem iPhone
deshalb nicht erreichbar, nur mit einer eigenen App (siehe unten).

### Was die Logs zeigten (Test vom 17.11.2026)

Nach jeder Rückkehr stand eine neue Verbindung binnen etwa 1 bis 2 Sekunden: neuer WebSocket, `event=join`, dann `event=connected`.
Der Weg über den TURN-Server (`route=relay/srflx/udp`) funktionierte ebenfalls. Verbesserungsbedarf gab es bei der Erkennung: Ein
toter Socket fiel dem Browser erst spät auf, und nach einem Abbruch wartete die Seite bis zu 30 Sekunden (Backoff).

### Was jetzt anders ist

- **Sofort prüfen:** `visibilitychange` (Seite wieder sichtbar). Ist der Socket zu, wird sofort neu verbunden. War die Pause länger
  als 2 Sekunden, schickt die Seite einen Ping und verbindet nach 2 Sekunden ohne Antwort neu (`resumeAfterBackground`).
- **Sofort verbinden** (`reconnectNow`): ohne die Wartezeit nach einem Abbruch; der alte Socket verliert seine Handler, damit er
  nicht später ein zweites Mal aufbaut.
- **Stiller Socket:** Der Server beantwortet `ping` schon länger mit `pong`, die Seite wertete das nie aus. Jetzt gilt: Kommt 15
  Sekunden keine Antwort, wird neu verbunden (nicht im Hintergrund, dort laufen Timer gedrosselt). Der Vergleich „kam eine Antwort?“
  läuft über einen Zähler, nicht über einen Zeitstempel (der konnte in derselben Millisekunde gleich sein; fiel im Test auf).
- **Netzwechsel:** Das Ereignis `online` löst den Neuaufbau sofort aus (WLAN ↔ Mobilfunk).
- **Mikrofon und Kamera neu holen** (`refreshLocalTrack`): Nach der Pause sind Spuren oft beendet oder vom System stumm. Eine stumme
  Spur bekommt 1,2 Sekunden, um von selbst zurückzukommen, sonst wird sie neu geholt und in alle bestehenden Verbindungen eingesetzt
  (`replaceTrack`). „Stumm“ bleibt stumm. Nichts wird angefordert, was nie erlaubt war, und nach „Verlassen“ nichts mehr.
- **Bildschirm wach halten** (`requestWakeLock`): Solange man im Meeting ist, sperrt das Handy den Bildschirm nicht von selbst. Das
  System gibt den Wachhalter im Hintergrund frei, deshalb wird er nach der Rückkehr neu angefordert.
- **Hinweis in der Lobby** (nur Touchgeräte): „Bleib in dieser Seite, solange das Meeting läuft. Wechselst du in eine andere App, …“

## Geprüft

Nicht Teil der CI (Browser), mit den echten Funktionen der Seite:

- **Radierer** in Chrome: Stift und Radierer auf weißem Blatt und auf einem roten „PDF“-Hintergrund, alte gegen neue Fassung. Alt:
  radierte Stelle `[0,0,0,0]` (durchsichtig, auch im PDF). Neu: Blatt bzw. PDF bleibt (`[255,255,255,255]` / `[255,0,0,255]`),
  unberührte Striche bleiben schwarz, ein neuer Strich über der radierten Stelle erscheint, ein Radierstrich der Gegenseite wirkt.
- **Rückkehr** mit einem Fake-Socket und Fake-Spuren (24 Prüfungen): Neuaufbau, Ping und Antwort, kurzer Wechsel, vor dem Beitritt
  und nach „Verlassen“, Takt ohne Antwort, Takt im Hintergrund, Spur neu holen und einsetzen, Wachhalter nur einmal. Dazu zehn
  Fehler gezielt eingebaut: neun werden von den Prüfungen bemerkt, einer ist gleichwertig (`connectWS` löscht denselben Timer
  ohnehin). Im ersten Durchlauf fiel auf, dass der Schutz „nach Verlassen das Mikrofon nicht neu holen“ keinen Test hatte; ergänzt.
  Außerdem zeigte der erste Lauf den Vergleich über den Zeitstempel (siehe oben).

Server (CI): `apps/meeting/test_room_whiteboard_and_background.py` (die Korrekturen stehen in der ausgelieferten Seite). Gegen die
alte Seite schlagen alle zehn Tests fehl.

## Nicht gelöst und offen

- **iPhone im Hintergrund:** Mikrofon und Verbindung pausieren weiterhin, solange eine andere App vorn ist. Verbessert ist nur, wie
  schnell es danach weitergeht. Eine echte Lösung wäre eine **eigene App** (z. B. mit Capacitor und Hintergrundmodus „audio“). Das
  ist ein eigenes Projekt (App-Store-Konto, Prüfung, Pflege) und eine Entscheidung von Andreas.
- Nicht ausprobiert: Bild-in-Bild für die Videokachel. Es könnte die Seite auf dem iPhone länger am Leben halten, ist aber nicht
  verlässlich belegt.
- Wer in eine andere App wechselt, erscheint bei der Gegenseite als „Verbindung unterbrochen“ und dann als ausgetreten. Eine
  Meldung „im Hintergrund“ bräuchte eine neue Nachricht im Server (`consumers.py`) und wurde nicht gebaut.

## Code

| Teil | Ort |
|---|---|
| Ebene, `redrawAll`, `drawStroke(stroke, ctx)`, Radierer, `requestWbRedraw` | `apps/meeting/templates/meeting/room.html` |
| `connectWS` (Takt, `pong`), `reconnectNow`, `refreshLocalTrack`, `resumeAfterBackground`, `requestWakeLock`, Lobby-Hinweis | `apps/meeting/templates/meeting/room.html` |
| Tests | `apps/meeting/test_room_whiteboard_and_background.py` |

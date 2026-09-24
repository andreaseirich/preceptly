# Content-Security-Policy

**Stand:** 24.09.2026 — Melde-Modus aktiv, noch nicht scharf geschaltet.

Die Content-Security-Policy sagt dem Browser, aus welchen Quellen eine Seite
etwas laden darf. Sie ist die wirksamste Bremse gegen eingeschleusten
Fremdcode: Selbst wenn es jemand schafft, ein `<script src="…">` in eine Seite
zu bekommen, lädt der Browser es nicht.

## Wo steht sie

| | |
|---|---|
| Richtlinie, Nonce und Middleware | `backend/apps/core/csp.py` |
| Nonce für die Vorlagen | Context-Processor `csp_nonce` in `backend/apps/core/context_processors.py` |
| Ersatz für Inline-Handler | `backend/apps/core/static/js/actions.js` |
| Meldestelle für Verstöße | `backend/apps/core/views_csp.py`, URL `/csp-report/` |
| Wächter-Tests | `backend/apps/core/tests/test_csp_nonce.py` |
| Schalter | Umgebungsvariable `CSP_REPORT_ONLY` (Standard: `1` = nur melden) |

## Skripte: nur mit Nonce

Jede Antwort bekommt eine neue Zufallszahl (Nonce). Sie steht im Kopf der
Richtlinie und an jedem `<script>` der Seite:

```html
<script nonce="{{ csp_nonce }}">…</script>
<script src="{% static 'js/…' %}" nonce="{{ csp_nonce }}"></script>
```

Eingeschleuster Code kennt die Nonce nicht und läuft deshalb nicht. Zusätzlich
steht `'strict-dynamic'` in der Richtlinie: Aktuelle Browser erlauben dann nur
Skripte mit Nonce und was diese per JavaScript nachladen. Hostliste und
`'unsafe-inline'` bleiben nur als Rückfall für ältere Browser drin und zählen
in aktuellen nicht.

**Inline-Handler gibt es nicht mehr.** `onclick="…"`, `onsubmit="…"` und
`href="javascript:…"` können keine Nonce tragen und würden blockiert. Ihre
Aufgabe übernehmen Daten-Attribute, die `actions.js` auswertet:

| statt | jetzt |
|---|---|
| `onclick="setTool('pen')"` | `data-click="setTool" data-click-args='["pen"]'` |
| `onclick="switchTab('chat', this)"` | `data-click="switchTab" data-click-args='["chat", "$el"]'` |
| `onchange="jumpToDate(this.value)"` | `data-change="jumpToDate" data-change-args='["$value"]'` |
| `onsubmit="return confirm('…')"` | `data-confirm="…"` am Formular |
| `onchange="this.form.submit()"` | `data-autosubmit` |
| `onclick="event.stopPropagation()"` | `data-stop-propagation` |
| `href="javascript:history.back()"` | echtes `href` als Rückfall plus `data-history-back` |

Alle Varianten stehen im Kopf von `actions.js`. Aufgerufen werden globale
Funktionen — dieselbe Voraussetzung wie früher bei den Inline-Handlern.
Elemente, die JavaScript zur Laufzeit baut, bekommen ihre Listener am besten
direkt per `addEventListener` (Beispiel: Dokumentliste im Meeting-Raum).

**Wächter:** `test_csp_nonce.py` durchsucht alle Vorlagen und schlägt fehl,
sobald ein Inline-Handler, ein `javascript:`-Link oder ein `<script>` ohne Nonce
auftaucht.

## Warum zuerst nur melden

Im Melde-Modus schickt der Browser den Kopf
`Content-Security-Policy-Report-Only`: Er blockiert nichts, meldet aber jeden
Verstoß an `/csp-report/`. Das ist für den Videoraum entscheidend — eine zu
enge Richtlinie würde dort ein laufendes Meeting beenden, statt nur eine
Kleinigkeit kaputt zu machen.

Verstöße landen als Warnung im Log (`CSP-Verstoß: …`). Gleiche Verstöße werden
nur einmal pro Stunde protokolliert, damit eine Browser-Erweiterung oder ein
Bot die Logs nicht flutet.

Verstöße ansehen:

```bash
railway logs --service preceptly --since 24h | grep CSP-Verstoß
```

## Was die Richtlinie erlaubt

- `default-src 'self'` — alles nur von der eigenen Domain.
- `script-src`: Nonce plus `'strict-dynamic'` (siehe oben); dahinter als
  Rückfall für ältere Browser `'self'`, die Quellen des Widerrufsformulars und
  `'unsafe-inline'`.
- `style-src` zusätzlich `'unsafe-inline'` — Inline-Styles stecken derzeit in
  fast jeder Vorlage — und das Stylesheet des Widerrufsfensters.
- `img-src`/`media-src` zusätzlich `data:` und `blob:` — Vorschaubilder und
  Videoströme im Meeting-Raum.
- `worker-src 'self' blob:` — pdf.js legt seinen Arbeitsprozess als Blob an.
- `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`,
  `form-action 'self'` — Plugins, Einbettung in fremde Seiten, untergeschobene
  Basis-URLs und Formular-Umleitungen sind ausgeschlossen.

Offen bleibt `'unsafe-inline'` bei **Styles**: Inline-Styles stecken in fast
jeder Vorlage. Das ist deutlich weniger gefährlich als bei Skripten, wäre aber
der nächste Schritt.

## Widerrufsformular (e-Recht24)

Der Widerrufs-Button im Fußbereich ist gesetzlich vorgeschrieben. Er braucht
mehr fremde Quellen, als auf den ersten Blick sichtbar ist — und die
wichtigste zeigt sich erst beim **Absenden**:

| Richtlinie | Quelle | wofür |
|---|---|---|
| `script-src`, `style-src`, `connect-src`, `frame-src` | `https://widerrufsbutton-cdn.e-recht24.de` | Button-Skript, Fenster-Skript und -Stylesheet |
| `connect-src` | `https://widerrufsbutton.e-recht24.de` | **Abschicken des Widerrufs** (`/api/v1/revocations`) |
| `script-src` | `https://cdn.jsdelivr.net` | Friendly-Captcha-Widget (`friendly-challenge@0.9.14`) |
| `script-src` | `'wasm-unsafe-eval'` | Rechenkern des Captchas (WebAssembly) — erlaubt **kein** `eval()` |
| `connect-src` | `https://api.friendlycaptcha.com` | Captcha-Rätsel abholen |
| `worker-src` | `blob:` | Captcha rechnet in einem Blob-Worker |

**Wie ermittelt (24.09.2026):** Der Melde-Modus hatte am ersten Tag nur das
Stylesheet gemeldet — das Fenster öffnet ja kaum jemand. Also das Fenster
einmal selbst im Browser geöffnet (ohne das Captcha anzufassen, ohne
abzuschicken) und die Meldungen in der Konsole mitgelesen. Die Adresse fürs
Absenden steht in `revocation-modal.min.js` als `apiUrl` und liegt auf einem
**anderen Host** als das CDN. Scharf geschaltet mit der ersten Fassung der
Richtlinie hätte sich das Fenster also geöffnet, der Widerruf wäre aber beim
Absenden stillschweigend blockiert worden.

**Warum das trotz Hostliste sicher ist:** Mit `'strict-dynamic'` ignorieren
aktuelle Browser die Hostliste. Das e-Recht24-Skript im Fußbereich trägt die
Nonce und darf deshalb Fenster und Captcha nachladen — egal, welche
Widget-Version e-Recht24 gerade einbindet. Ein eingeschleustes
`<script src="https://cdn.jsdelivr.net/…">` hat dagegen keine Nonce und wird
abgewiesen. Die Hostliste gilt nur noch für ältere Browser ohne
`'strict-dynamic'`.

**Nach Änderungen bei e-Recht24 erneut prüfen:**

```bash
curl -s https://widerrufsbutton-cdn.e-recht24.de/<shop-id>/revocation-modal.min.js \
  | grep -oE 'https://[a-zA-Z0-9.-]+' | sort -u
```

Jede neue Adresse dort muss in die Richtlinie.

## Scharf schalten

1. Ein paar Tage Melde-Modus laufen lassen und die Logs durchsehen.
2. Fehlende Quellen in `POLICY_DIRECTIVES` ergänzen — oder besser: die Stelle
   im Code so ändern, dass sie ohne die fremde Quelle auskommt.
3. `railway variables --service preceptly --set "CSP_REPORT_ONLY=0"`.
4. Direkt danach ein echtes Meeting öffnen und prüfen: Kamera, Mikrofon,
   Bildschirmfreigabe, PDF-Anzeige, Chat.
5. Das Widerrufsfenster öffnen und prüfen, dass das Captcha lädt und keine
   CSP-Meldung in der Konsole erscheint.

Zurückschalten geht jederzeit mit `CSP_REPORT_ONLY=1`.

# Content-Security-Policy

**Stand:** 23.09.2026 — Melde-Modus aktiv, noch nicht scharf geschaltet.

Die Content-Security-Policy sagt dem Browser, aus welchen Quellen eine Seite
etwas laden darf. Sie ist die wirksamste Bremse gegen eingeschleusten
Fremdcode: Selbst wenn es jemand schafft, ein `<script src="…">` in eine Seite
zu bekommen, lädt der Browser es nicht.

## Wo steht sie

| | |
|---|---|
| Richtlinie und Middleware | `backend/apps/core/csp.py` |
| Meldestelle für Verstöße | `backend/apps/core/views_csp.py`, URL `/csp-report/` |
| Schalter | Umgebungsvariable `CSP_REPORT_ONLY` (Standard: `1` = nur melden) |

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
- `script-src` zusätzlich `'unsafe-inline'` und
  `https://widerrufsbutton-cdn.e-recht24.de`. Das Fremdskript liefert den
  gesetzlich vorgeschriebenen Widerrufs-Button im Fußbereich; ohne diese Quelle
  ist die Schaltfläche tot.
- `style-src` zusätzlich `'unsafe-inline'` — Inline-Styles stecken derzeit in
  fast jeder Vorlage.
- `img-src`/`media-src` zusätzlich `data:` und `blob:` — Vorschaubilder und
  Videoströme im Meeting-Raum.
- `worker-src 'self' blob:` — pdf.js legt seinen Arbeitsprozess als Blob an.
- `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`,
  `form-action 'self'` — Plugins, Einbettung in fremde Seiten, untergeschobene
  Basis-URLs und Formular-Umleitungen sind ausgeschlossen.

`'unsafe-inline'` bei Skripten ist der wunde Punkt: Solange es drinsteht,
schützt die Richtlinie nicht gegen eingeschleusten Inline-Code. Das fällt erst
weg, wenn die Vorlagen ihre Inline-Skripte über Nonces ausweisen.

## Scharf schalten

1. Ein paar Tage Melde-Modus laufen lassen und die Logs durchsehen.
2. Fehlende Quellen in `POLICY_DIRECTIVES` ergänzen — oder besser: die Stelle
   im Code so ändern, dass sie ohne die fremde Quelle auskommt.
3. `railway variables --service preceptly --set "CSP_REPORT_ONLY=0"`.
4. Direkt danach ein echtes Meeting öffnen und prüfen: Kamera, Mikrofon,
   Bildschirmfreigabe, PDF-Anzeige, Chat.

Zurückschalten geht jederzeit mit `CSP_REPORT_ONLY=1`.

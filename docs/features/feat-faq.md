# FAQ für Tutoren und Familien

**Stand:** 02.10.2026 · Auftrag von Andreas: beide FAQ gründlich erweitern.

## Wo

| Seite | Template | Zugang |
|---|---|---|
| FAQ für Tutoren | `apps/core/templates/core/faq.html` | öffentlich, steht in der Sitemap |
| Hilfe & FAQ für Schüler und Eltern | `apps/portal/templates/portal/faq.html` | nur mit Portal-Anmeldung |

Beide Seiten sind fest auf Deutsch geschrieben, wie der Rest des Portals.

## Regeln für Änderungen

- **Jede Antwort muss zum Code passen.** Vor dem 02.10.2026 stand in der FAQ
  noch, das Löschen einer Rechnung setze die Stunden zurück, obwohl sich
  versendete Rechnungen seit 28.09.2026 nicht mehr löschen lassen.
- **Zahlen aus dem Code** (Dokumente und Portal-Buchungen im Starter-Tarif,
  Hinweisgrenzen im kostenlosen Tarif) prüft `test_faq_pages.py` gegen
  `feature_flags.py`. Ändert sich eine Grenze, schlägt der Test an.
- **Preise** stehen zusätzlich auf der Startseite (`landing.html`). Beide
  Stellen gemeinsam ändern.
- **Themenliste oben:** kein `nav`-Element verwenden. Beide Basis-Templates
  gestalten jedes `nav` als Hauptnavigation. Stattdessen `role="navigation"`.
- **Kommentare** mit `{# … #}` nur einzeilig. Mehrzeilige erscheinen als Text.
- **Sprunglinks im Menü** (`base.html`) zeigen auf `#einnahmen`,
  `#rechnungen`, `#stunden`, `#steuern`, `#berichte` und
  `#gestaffelte-verguetung`. Diese IDs nicht umbenennen.

## Bewusst so beantwortet

- **Absagen und Verschieben im Portal:** Der Tutor bekommt keine eigene
  Nachricht, und ein abgesagter Termin wird gelöscht. Beide FAQ sagen das
  offen. Ob das so bleiben soll, ist offen (siehe unten).
- **Datenschutz:** keine Angaben zu Hosting oder Technik, nur der Verweis auf
  die Datenschutzerklärung. Die Rechtstexte kommen von eRecht24.
- **Konto löschen:** Tutoren wenden sich an die Kontaktdaten im Impressum,
  Familien an ihren Tutor. Eine Löschfunktion zum Selbstbedienen gibt es nicht.

## Offen

- Benachrichtigung des Tutors bei Absage und Verschiebung im Portal.
- Abgesagte Termine als „abgesagt“ aufbewahren statt löschen, damit
  nachvollziehbar bleibt, wer wann abgesagt hat.

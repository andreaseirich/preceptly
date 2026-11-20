# Designsystem „Kladde“: Überarbeitung von Gestaltung, Texten und Technik

**Stand:** 20.11.2026 · Auftrag von Andreas: Preceptly „gestalterisch, inhaltlich und technisch“ vollständig überarbeiten. Nicht veröffentlicht,
nicht in der Produktion getestet: Der Stand liegt auf dem Zweig `redesign/preview` in einer eigenen Arbeitskopie ohne Verbindung zu GitHub und Railway
(`/root/agents/tutorflow-redesign`).

## Ausgangslage

Alle Seiten sahen aus wie eine Standardvorlage: Systemschrift, graue Schaltflächen, Emojis als Symbole, ein Marineblau-Balken oben. Das CSS bestand aus
zwei fast gleichen, je rund 400 Zeilen langen Inline-Blöcken (`core/base.html`, `portal/base.html`) und über 450 Inline-`style`-Attributen. Die
Startseite enthielt eine unbelegte Zahl („2–3 Stunden pro Woche“), ein Etikett „Premium“, das es als Tarif nicht gibt, und einen leeren Abschnitt, solange
es keine Bewertungen gab.

## Konzept: Kladde

Preceptly ist das Heft, in dem ein Nachhilfelehrer seine Woche führt. Daraus folgt die Gestaltung:

| Thema | Name | Bedeutung |
|---|---|---|
| hell | **Papier** | warmes Blatt (`#f3efe6`), Karten in `#fffdf8`, Tinte in Marine (`#1c2833`) |
| dunkel | **Tafel** | Schiefergrün (`#0f1a1c`), Kreide (`#e9f0ea`), Akzent Türkis (`#66d6bb`) |
| Akzent | Türkis aus dem Logo, abgedunkelt für Text (`#0b6e5c`) | Links, Hauptschaltflächen |
| Hervorhebung | **Textmarker** (`#f4d03f`) | nur als Fläche hinter Tinte, nie als Schriftfarbe |
| Schrift | **Source Serif 4** für Titel, **Source Sans 3** für Text | beide selbst ausgeliefert (SIL OFL), keine Anfrage an Dritte |
| Dekor | liniertes Papier mit Randlinie im Kopfbereich der Startseite, Textmarker-Strich über Anmeldekarten | sonst bleibt die Oberfläche ruhig |

Die Markenfarbe (Marine, Türkis) und das Logo bleiben. Hell und dunkel folgen der Geräteeinstellung, solange nichts gespeichert ist; der Umschalter
speichert die Wahl wie bisher (`localStorage`, Schlüssel `theme` und `portal-theme`).

## Aufbau der Stylesheets

Alles liegt unter `backend/apps/core/static/core/css/`. Jede Datei hat eine Aufgabe und bleibt klein.

| Datei | Inhalt |
|---|---|
| `tokens.css` | Farben (hell, dunkel, „Gerät dunkel“), Schrift, Abstände, Radien; **eine Stelle für alle Werte**. Alte Namen (`--bg-primary`, `--accent`, …) bleiben als Aliase |
| `base.css` | Elemente: Typografie, Links, Fokus, Formulare, Tabellen |
| `components.css` | Schaltflächen, Hinweise, Marken, Dialoge, Logo-Umschaltung, Theme-Knopf |
| `shell.css` | Tutor-App: Kopfzeile, Menü, Statusbänder, Inhaltsfläche, Fußzeile |
| `portal-shell.css` | Portal: Kopfzeile ohne Aufklappmenüs, schlichte Fläche, Karten |
| `auth.css` | Anmelden, Registrieren, Passwort, Fehlerseiten (eine Karte in der Mitte) |
| `landing.css` | Startseite |
| `calendar-theme.css` | Kalender in der Tafel-Ansicht (aus `base.html` ausgelagert) |

Die Schriften liegen unter `apps/core/static/fonts/` (mit `LICENSES.md`), die Icons als **ein** Python-Modul `apps/core/icon_paths.py` (Zeichnungen aus
Lucide, ISC). `{% icon "users" %}` verweist auf ein einmal je Seite eingebettetes Sprite (`{% icon_sprite %}`); Icons sind Dekor und stehen mit Text daneben oder
mit `aria-label` am Knopf.

## Was sich inhaltlich geändert hat

- **Startseite neu geschrieben.** Kopfbereich mit Tagesplan-Zeichnung (zeigt die echte Funktion: Konflikterkennung), Ablauf in drei Schritten, Funktionen **nach
  Tarif sortiert** (Free, ab Starter, ab Pro) gemäß `feature_flags.FEATURE_MIN_TIER`, Datenschutz-Streifen, Preise, Gründergeschichte, Demo.
- **Entfernt:** „Private Tutoren verlieren 2–3 Stunden pro Woche …“ (ohne Beleg), „Kostet weniger als eine Stunde – spart dir Stunden Verwaltungsaufwand“
  und „der Wechsel rechnet sich schon bei der ersten Rechnung“ (nicht belegbar), das Etikett „Premium“ an Funktionen (es gibt Free, Starter, Pro, Business).
- **Neu genannt:** Die Grenzen des kostenlosen Tarifs (bis zu 5 Schüler, bis zu 8 Rechnungen im Monat). Sie wurden durchgesetzt (`free_limits.py`,
  `billing/views.py`), standen aber nirgends. Ein Test (`test_page_structure.LandingFactsTest`) hält Seite und Konstanten gleich.
- **Anrede:** In der Tutor-Oberfläche steht überall „du“. 33 Texte waren förmlich („Möchten Sie …“, „Bitte wählen Sie …“) und wurden in der `.po` umgestellt.
  Rechtstexte, Meldungen für Betreiber und „Sie“ im Sinn von „sie (Mehrzahl)“ bleiben. Das Elternportal spricht Eltern weiter mit „Sie“ an (siehe offene Punkte).
- **Demo-Hinweis:** „Daten werden stündlich zurückgesetzt“ stimmte nie; es ist täglich (seit Commit 2470578).
- **Vertragsbezeichnung:** „28.00€/unit“ in der deutschen Oberfläche heißt jetzt „28,00 €/Einheit“ (Zahl lokalisiert, `unit` übersetzt).
- Übersetzbare Titel und Beschriftungen, die fest auf Deutsch standen (Anmelden, Registrierung, Fußzeile, Löschseite), folgen jetzt der Sprache.

## Technische Funde und Korrekturen

| Fund | Ursache | Korrektur |
|---|---|---|
| `GET /students/<id>/delete/` lieferte **HTTP 500** | Die View ist eine `DeleteView` auf `Contract` und liefert `object`; die Vorlage las `student.pk` für „Abbrechen“ | Vorlage nutzt `object`; der Name im Fragesatz war außerdem leer. Test `apps/students/test_delete_confirm.py` |
| „Abbrechen“ beim Verschieben einer Stunde tat nichts | `href` war `javascript:history.back()`, die CSP blockiert das; zusätzlich wurde `?next=` ungeprüft in den Link übernommen | `data-history-back` mit echtem `href` auf die Stunde; `next` wird nicht mehr ausgegeben |
| Datenschutzerklärung und Impressum ohne `<h1>` (wenn eRecht24 nicht erreichbar ist) | Rückfalltext hatte nur `<h2>` | `<h1>` im Rückfall |
| Beschriftungen ohne Feld (KI-Hinweis, PDF-Upload, Kalender-Abo-Adresse) | `<label>` ohne `for` / Feld ohne Namen | `for`/`id`, `aria-label` |
| Menü mit `role="menu"` ohne Pfeiltasten-Steuerung | falsches ARIA-Muster | Muster „aufklappbarer Bereich“ (`aria-expanded`, `aria-controls`), aktuelle Seite mit `aria-current` |
| Theme-Knopf ohne Zustand, Logo doppelt vorgelesen | – | `aria-pressed`; zweite Logo-Fassung mit `alt=""` |
| Kalenderblöcke: weiß auf Orange (2,2:1), Gelb auf Türkis, feste Farben | Inline-Farben | Klassen und Tokens (`lesson-block--planned|taught|paid`, `blocked-time-block`) |
| `<html lang="de">` fest, Fußzeilen-Beschriftung fest deutsch | – | Sprache folgt der Anfrage; Beschriftungen übersetzbar |
| Suchfeld in Listen sah deaktiviert aus | Hintergrund = Seitenfarbe | `--bg-secondary` |

## Tests

Neu (mit Mutationstest geprüft: 18 verschiedene eingebaute Fehler, alle werden gefangen; der Wochenansicht-Test war zunächst zu schwach, weil er den Klassennamen auch im CSS der Seite fand, und wurde verschärft):

- `apps/core/tests/test_design_tokens.py` rechnet die Kontraste (WCAG 2.1 AA) **aus `tokens.css`** nach, in beiden Themen, und gleicht den Block „Gerät dunkel“ mit
  `data-theme="dark"` ab. Prüft, dass die Schriften als Datei vorhanden sind.
- `apps/core/tests/test_icons.py`: nur bekannte Icon-Namen, **kein `{% icon %}` in einem Attribut**, `{% load icons %}` vorhanden, keine Emojis als Icons in Seitenvorlagen.
- `apps/core/tests/test_page_structure.py`: genau eine `<h1>` je öffentlicher Seite in DE und EN, Fakten der Startseite gegen den Code, Anrede, Anmeldeseiten.
- `apps/core/tests/test_theme_shell.py`: Sprunglink, Landmarken, Theme-Knopf, Logo, Menü, Sprachwahl.
- `apps/students/test_delete_confirm.py`, `apps/lessons/tests/test_week_block_colours.py`, `apps/lessons/tests/test_reschedule_cancel_link.py`.
- Angepasst, weil sich Markup bewusst geändert hat (die Absicht der Tests bleibt): `test_contrast_tokens.py` (liest `tokens.css`),
  `test_calendar_site_texts.py` (Gruppe „Ab dem Pro-Tarif“; zusätzlich: Meetingräume und KI stehen nur dort), `test_faq_pages.py` (das Icon-Sprite ist kein
  Sprunglink), `test_i18n.py`, `test_week_view_click_behavior.py` (SVG statt Emoji), `portal/test_login_page.py`, `portal/test_week_picker.py`,
  `portal/tests_portal.py` (Meldung per `role="alert"`, Konto bleibt unaktiviert), `test_csp_nonce.py` (erkennt jetzt auch `javascript:` in Vorlagenausdrücken).

## Vorschau, Veröffentlichung, Rücknahme

**Vorschau:** Es gibt absichtlich keinen Vorschau-Server. Die Seiten werden mit dem Django-Testclient aus dem Zweig gerendert und als statische Spiegelung
abgelegt (`render_site.py`); die Screenshots lesen die Dateien direkt. Damit kann nichts in die Produktion gelangen und nichts indexiert werden.

**Veröffentlichen** (erst nach ausdrücklicher Freigabe von Andreas):

1. Zweig prüfen: `git log main..redesign/preview`, volle Test-Suite, CI.
2. Auf dem ai-server in `/root/agents/tutorflow`: `git fetch /root/agents/tutorflow-redesign redesign/preview && git merge --no-ff FETCH_HEAD` (oder als Pull Request).
3. `bash /root/bin/preceptly-push.sh` (wartet auf CI und Railway). Railway deployt erst bei grünem CI.
4. Danach live prüfen: Startseite, Anmeldung, Dashboard, Wochenansicht, Portal-Login, 404, jeweils hell und dunkel, DE und EN.

**Zurücknehmen:** `git revert -m 1 <Merge-Commit>` und erneut pushen. Es gibt **keine Datenbankänderung** und keine Migration; die neuen Dateien (Stylesheets,
Schriften) liegen nur im Code. Der Service Worker (`sw.js`) legt `/static/` „cache first“ ab, aber die Dateinamen tragen einen Hash (Manifest-Speicher): Nach Deploy oder Zurücknehmen gibt es keine veralteten Stylesheets, HTML kommt immer zuerst aus dem Netz.

## Offene Punkte

- Tabellen scrollen auf dem Handy seitlich statt als Karten (betrifft alle Listen; eigener Auftrag).
- Der Meetingraum (`meeting/room.html`) hat eigene Oberfläche und Emojis in den Schaltflächen; nur Farben/Schrift gehen über die Tokens. Er wurde bewusst nicht
  angefasst (WebRTC, gerade erst repariert).
- E-Mail-Vorlagen und die PDF-Rechnung sind unverändert (E-Mail-Clients vertragen kein externes CSS).
- Das Portal ist komplett deutsch fest verdrahtet (kein `{% trans %}`); eine englische Fassung gibt es dort nicht.
- Förmliche Anrede („Sie“) im Elternportal: Eltern und Schüler teilen sich das Portal; Entscheidung über „du“/„Sie“ liegt bei Andreas.
- Standardmäßig bleiben Hinweisfenster („in aktiver Entwicklung“) und Installationsbanner wie bisher; sie decken beim ersten Besuch Inhalt ab.

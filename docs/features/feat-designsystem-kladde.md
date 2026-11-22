# Designsystem „Kladde“: Überarbeitung von Gestaltung, Texten und Technik

**Stand:** 22.11.2026 · Auftrag von Andreas: Preceptly „gestalterisch, inhaltlich und technisch“ vollständig überarbeiten.
**Veröffentlicht am 22.11.2026** als `0f4e7e2` auf `main` (Push 14:10 UTC, von Railway ausgeliefert 14:24 UTC; Abschnitt „Veröffentlichen und Zurücknehmen“). Entwickelt wurde es auf dem Zweig `redesign/preview`
in der Arbeitskopie `/root/agents/tutorflow-redesign`. Am selben Tag folgte als `2e7d597` (ausgeliefert 17:17 UTC) die Korrektur der Kopfzeile im dunklen Thema samt Browser-Regressionsprüfung; die Behebung der übrigen Auffälligkeiten der
Live-Prüfung steht im Abschnitt „Auffälligkeiten der Live-Prüfung“.
**Tests:** vollständig 1824 Tests OK (21.11., Stand `6832107`) und 1834 Tests OK im Pre-Push-Hook der Veröffentlichung (22.11., `0f4e7e2`, jeweils 5 übersprungen); zu den Änderungen danach siehe „Tests“ und
„Nachträgliche Korrektur“.

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
| Hervorhebung | **Textmarker** (`#f4d03f`) | hell als Strich hinter Tinte, dunkel als volle Fläche mit dunkler Schrift; nie als Schriftfarbe |
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
| `components.css` | Schaltflächen, Hinweise, Marken, Dialoge, Logo-Umschaltung, Theme-Knopf, mobile Tabellen |
| `shell.css` | Tutor-App: Kopfzeile, Menü, Statusbänder, Inhaltsfläche, Fußzeile |
| `portal-shell.css` | Portal: Kopfzeile ohne Aufklappmenüs, schlichte Fläche, Karten |
| `auth.css` | Anmelden, Registrieren, Passwort, Fehlerseiten (eine Karte in der Mitte) |
| `landing.css` | Startseite |
| `calendar-theme.css` | Kalender in der Tafel-Ansicht (aus `base.html` ausgelagert) |

Die Schriften liegen unter `apps/core/static/fonts/` (mit `LICENSES.md`), die Icons als **ein** Python-Modul `apps/core/icon_paths.py` (Zeichnungen aus
Lucide, ISC). `{% icon "users" %}` verweist auf ein einmal je Seite eingebettetes Sprite (`{% icon_sprite %}`); Icons sind Dekor und stehen mit Text daneben oder
mit `aria-label` am Knopf.

## Entscheidungen von Andreas (21.11.2026) und ihre Umsetzung

| Entscheidung | Umsetzung |
|---|---|
| **Free-Tarif:** „Free“ und die Zahlen 5 Schüler / 8 Rechnungen passen, sofern sie dem tatsächlichen Verhalten entsprechen | Das tatsächliche Verhalten wurde im Code geprüft (nächster Abschnitt). Es ist ein **Hinweis, keine Sperre**; der Wortlaut sagt deshalb „Gedacht für bis zu 5 Schülerverträge / 8 Rechnungen im Monat“ und nennt Auslöser und Zählregeln (gezählt werden Verträge, nicht verschiedene Personen; nächster Abschnitt). „Free“ steht jetzt überall in der Oberfläche (Startseite, FAQ, Einstellungen, Meldungen, Demo-Zugang). Technische Tarifkennungen (`free`), Zahlungszuordnungen und Vertragsbedingungen sind unverändert |
| **Ansprache im Portal:** durchgehend „du“, auch gegenüber Eltern; Rechtstexte und verbindliche Dokumente unverändert | „Deine Kinder“, „mit deinem Konto“ im Elternportal; „Was möchtest du löschen?“; Meldung an Tutoren in `students/views.py`. **Unverändert** bleiben: Rechtstexte, Abo-Bestätigung und Widerruf (`core/email/subscription_confirmation.txt`, `revocation_confirm.html`, `views_erecht24_revocation.py`), die Zahlungsaufforderung im PDF (`pdf_service.py`), die Datenschutz-Overrides (`legal_overrides.py`) und Meldungen für Betreiber (`ai/client.py`, Verwaltungsbefehle). Die „Sie“ in der Portal-FAQ meinen „sie (Mehrzahl)“ |
| **Mobile Tabellen:** seitlich scrollbar genügt; nur der Tabellenbereich scrollt, Aktionen bleiben erreichbar, weitere Spalten erkennbar | Bis 820 px wird die Tabelle selbst zum Scrollbereich (`overflow-x: auto`, `overscroll-behavior-x: contain`), die Seite scrollt nicht mit. Schatten an den Rändern zeigen verborgene Spalten. Bis 640 px bleibt die letzte Spalte mit den Aktionen (Details, Bearbeiten, Löschen) rechts stehen (`position: sticky`), die Knöpfe stehen untereinander und halten die Spalte schmal. Browserprüfung am 390-px-Viewport: siehe unten |
| **Ausgenommene Bereiche:** Meetingraum, E-Mail-Vorlagen, PDF-Rechnung nicht neu gestalten; Regressionen durch gemeinsame Styles prüfen | Alle drei bringen ihr eigenes Gerüst mit und laden **keines** der neuen Stylesheets. Geprüft durch Dateivergleich (keine Änderung seit `ce2ea1f`) und durch einen Renderlauf im unveränderten und im neuen Stand (Abschnitt „Regressionsvergleich“): kein Unterschied außer Datenbank-Kennungen |
| **Portal nur Deutsch:** englische Portalübersetzung außerhalb des Auftrags; keine Sprachwahl darf eine englische Fassung versprechen | Das Portal hat keine Sprachwahl. Neue Middleware `apps/portal/language.py` stellt alle Adressen unter `/portal/` auf Deutsch (vorher bekam man mit englischem Sprachcookie eine Mischung, weil das Hinweisfenster der Basis übersetzbar ist). Die englische Start- und Anmeldeseite sagen: „The portal is currently available in German only.“ |

## Free-Tarif: was tatsächlich gezählt wird

Geprüft in `apps/core/free_limits.py`, `apps/billing/views.py`, `apps/core/feature_flags.py`, PRD und den bestehenden Tests; abgesichert durch
`apps/core/tests/test_free_tier_wording.py`.

- **Es sind weiche Grenzen.** Beim Anlegen des 6. Vertrags und der 9. Rechnung eines Kalendermonats erscheint ein Hinweis mit Link zu den bezahlten Tarifen, danach bei jedem
  weiteren Anlegen. Gespeichert wird trotzdem, es wird nichts gesperrt, und die Nutzung geht normal weiter. (Meine Aussage vom 20.11., die Grenzen würden „durchgesetzt“, war ungenau.)
- **Gilt nur für Free-Konten, die ab dem 02.07.2026 (12:00 UTC) angelegt wurden.** Ältere Free-Konten und alle bezahlten Tarife bekommen keinen Hinweis.
- **„Schüler“ sind Verträge, nicht Personen.** Es gibt keine eigene Schüler-Tabelle: Vor- und Nachname stehen am Vertrag (`Contract`) und sind nicht eindeutig. Gezählt wird `Contract` des Kontos:
  - Dieselbe Person mit zwei Verträgen (zum Beispiel zwei Fächer oder ein neuer Vertrag nach einem beendeten) **zählt zweimal**.
  - **Beendete** (`end_date` gesetzt) und **inaktive** (`is_active` aus) Verträge zählen mit, bis sie gelöscht werden; Löschen nimmt sie aus der Zählung. Früher stand in der Meldung „aktive Schüler“; das stimmte nicht.
  - Der Hinweis erscheint über „Schüler anlegen“ und über „Vertrag anlegen“, wenn bereits 5 Verträge bestehen (der 6. und jeder weitere löst ihn aus).
  - **Textkorrektur vom 21.11.2026 (`a0356f9`):** Startseite, FAQ, PRD und die Meldungen sagten „5 Schüler“, „Grenze erreicht“ und „für unbegrenzte Schüler/Rechnungen“. Das las sich wie eine Personenzahl und
    wie eine harte Grenze, obwohl ein Free-Konto nie gesperrt wird und ein Upgrade nichts Neues verspricht. Jetzt: „bis zu 5 Schülerverträge“, „Gezählt werden Verträge, nicht verschiedene Personen“, der
    Auslöser (6. Vertrag, 9. Rechnung) und „Gesperrt wird nichts“. **Die Zähllogik, Tarifkennungen, Zahlungszuordnungen und Vertragsbedingungen sind unverändert.**
- **Rechnungen:** Es zählt jede Rechnung, die **im laufenden Kalendermonat angelegt** wurde, unabhängig vom Zeitraum der abgerechneten Stunden. Alle Status zählen
  (Entwurf, versendet, bezahlt, storniert). **Stornorechnungen sind eigene Rechnungen und zählen mit:** Wer eine Rechnung aus dem Vormonat storniert, belegt eine Rechnung
  im laufenden Monat. Der Hinweis erscheint beim Anlegen über „Rechnung erstellen“; das Anlegen einer Stornorechnung zeigt ihn nicht, zählt aber.
- **Monatsgrenze:** Der Monat gilt in deutscher Zeit. Früher wurde der Monat aus UTC gelesen, die Datenbankabfrage aber in deutscher Zeit ausgewertet; in der ersten
  Stunde eines Monats (00:00–01:00 bzw. 02:00 Uhr Sommerzeit) blieb der Hinweis deshalb aus. Behoben in `invoices_created_this_month()`; Test an der Monatsgrenze.

## Was sich inhaltlich geändert hat

- **Startseite neu geschrieben.** Kopfbereich mit Tagesplan-Zeichnung (zeigt die echte Funktion: Konflikterkennung), Ablauf in drei Schritten, Funktionen **nach
  Tarif sortiert** (Free, ab Starter, ab Pro) gemäß `feature_flags.FEATURE_MIN_TIER`, Datenschutz-Streifen, Preise, Gründergeschichte, Demo.
- **Entfernt:** „Private Tutoren verlieren 2–3 Stunden pro Woche …“ (ohne Beleg), „Kostet weniger als eine Stunde – spart dir Stunden Verwaltungsaufwand“
  und „der Wechsel rechnet sich schon bei der ersten Rechnung“ (nicht belegbar), das Etikett „Premium“ an Funktionen (es gibt Free, Starter, Pro, Business), der Tarifname „Basic“.
- **Anrede:** In der Tutor-Oberfläche und im Portal steht überall „du“ (siehe Entscheidungen). 33 Texte waren förmlich und wurden in der `.po` umgestellt.
- **Tarifbeschreibung (21.11.2026, zweite Korrektur):** Free-Grenzen heißen „Schülerverträge“, beschreiben die Zählung nach Verträgen und stellen klar, dass nur Hinweise erscheinen (siehe „Free-Tarif“).
- **Demo-Hinweis:** „Daten werden stündlich zurückgesetzt“ stimmte nie; es ist täglich (seit Commit 2470578).
- **Vertragsbezeichnung:** „28.00€/unit“ in der deutschen Oberfläche heißt jetzt „28,00 €/Einheit“ (Zahl lokalisiert, `unit` übersetzt).
- Übersetzbare Titel und Beschriftungen, die fest auf Deutsch standen (Anmelden, Registrierung, Fußzeile, Löschseite), folgen jetzt der Sprache.

## Technische Funde und Korrekturen

| Fund | Ursache | Korrektur |
|---|---|---|
| `GET /students/<id>/delete/` lieferte **HTTP 500** | Die View ist eine `DeleteView` auf `Contract` und liefert `object`; die Vorlage las `student.pk` für „Abbrechen“ | Vorlage nutzt `object`; der Name im Fragesatz war außerdem leer. Test `apps/students/test_delete_confirm.py`, im Browser mit Abbrechen und echtem Löschen bestätigt |
| „Abbrechen“ beim Verschieben einer Stunde tat nichts | `href` war `javascript:history.back()`, die CSP blockiert das; zusätzlich wurde `?next=` ungeprüft in den Link übernommen | `data-history-back` mit echtem `href` auf die Stunde; `next` wird nicht mehr ausgegeben |
| Free-Hinweis zählte in der ersten Stunde eines Monats falsch | Monat aus UTC gelesen, Abfrage in deutscher Zeit | `timezone.localtime()` |
| Meldung „5 aktive Schüler“ | Es zählt jeder Vertrag | Wortlaut korrigiert |
| Portal mit englischem Sprachcookie halb englisch | Übersetzbares Hinweisfenster in einer sonst deutschen Basis | `PortalGermanMiddleware` |
| Datenschutzerklärung und Impressum ohne `<h1>` (wenn eRecht24 nicht erreichbar ist) | Rückfalltext hatte nur `<h2>` | `<h1>` im Rückfall |
| Beschriftungen ohne Feld (KI-Hinweis, PDF-Upload, Kalender-Abo-Adresse) | `<label>` ohne `for` / Feld ohne Namen | `for`/`id`, `aria-label` |
| Menü mit `role="menu"` ohne Pfeiltasten-Steuerung | falsches ARIA-Muster | Muster „aufklappbarer Bereich“ (`aria-expanded`, `aria-controls`), aktuelle Seite mit `aria-current` |
| Theme-Knopf ohne Zustand, Logo doppelt vorgelesen | – | `aria-pressed`; zweite Logo-Fassung mit `alt=""` |
| Kalenderblöcke: weiß auf Orange (2,2:1), Gelb auf Türkis, feste Farben | Inline-Farben | Klassen und Tokens (`lesson-block--planned|taught|paid`, `blocked-time-block`) |
| `<html lang="de">` fest, Fußzeilen-Beschriftung fest deutsch | – | Sprache folgt der Anfrage; Beschriftungen übersetzbar |
| Suchfeld in Listen sah deaktiviert aus | Hintergrund = Seitenfarbe | `--bg-secondary` |
| **Farben unter dem Grenzwert, die nur die Messung der gerenderten Seiten fand** (81 hell, 75 dunkel) | Ränder der Sprachwahl und der Listenfilter 1,4:1; feste Farben `#28a745`, `#dc3545`, `#6c757d`, `#4a9eff`, `#16a34a`, `#27ae60` in 24 Vorlagen; weiße Schrift auf dem hellen Rot des dunklen Themas (2,3:1); Sortiersymbol abgeblendet (2,0:1); Fokus auf Fußzeilen-Links 2,2:1 | Tokens `--on-danger`, `--input-border` an Eingabefeldern, `var(--success|danger|ink-soft|accent|warning)` statt fester Töne, kein Abblenden, heller Fokus in der Fußzeile; Wächter `test_component_colours.py` |

## Tests

**Vollständige Suite am 21.11.2026** auf dem Stand, der als Commit `6832107` festgeschrieben ist (alle Apps, mit `tools/runtests.sh`: `compilemessages -l de`, dann `manage.py test`
ohne Parallelbetrieb und mit den Umgebungsvariablen der CI): `Ran 1824 tests … OK (skipped=5)`, Beendigungscode 0. Fehlermeldungen im Protokoll („Anthropic request failed“)
stammen aus Tests, die den Fehlerpfad der KI-Anbindung ausüben; sie sind kein Testfehler. Die 5 Überspringungen sind Skip-Marken, die schon vor dieser Arbeit im
Bestand waren; dieser Zweig fügt keine hinzu (`git diff 8bc3a06 6832107` enthält keine neue Marke). `ruff check` und `ruff format --check` sind sauber (CI verlangt beides).

**Mutationstest** (`tools/mutate*.sh`: je Lauf ein Fehler eingebaut, der zuständige Test muss fehlschlagen, danach wird die Datei zurückgesetzt). Zweite Welle (Wortlaut,
Zählregeln, Monatsgrenze, Portalsprache, Tabellen, Farben, Fokus): **14 verschiedene Fehler, alle von mindestens einem Test gefangen**. Eine Mutation (Stornorechnungen nicht
mitzählen) griff im ersten Lauf nicht, weil der Mustertext nicht traf; sie wurde mit `mutate5.sh` einzeln wiederholt und gefangen. Die Fälle der ersten Welle (Löschseite, Tokens,
Wochenblöcke, Icons, Theme-Knopf, Anmeldeseiten, `javascript:`-Link) stehen in `mutate.sh`, `mutate2.sh`, `mutate3.sh`; ein Fall in `mutate.sh` („Textmarker als Schriftfarbe“) war ein
Leerlauf und wurde in `mutate2.sh` durch eine echte Mutation ersetzt. Eine Gesamtzahl über beide Wellen ist hier bewusst nicht angegeben.

**Nach der Textkorrektur (`a0356f9`)**, gezielt statt einer neuen Gesamtserie: `test_free_tier_wording`, `test_page_structure`, `students.test_free_plan_limits`, `calendar_sync.test_calendar_site_texts`,
`test_faq_pages`, `test_i18n`, `portal.test_portal_language`, `test_component_colours` und die App `billing` (193 Tests). Zwei neue Verhaltenstests schlugen zunächst fehl; Ursache war der Testaufbau (die
Meldung der ersten Anlage wartete in der Sitzung und erschien beim zweiten Aufruf zusätzlich), nicht das Programm. Nach der Korrektur lief die Datei erneut (28 Tests mit `test_landing_ai_claim`), alle
bestanden; die übrigen Dateien waren von der Korrektur nicht berührt. Mutationstest dazu (`py-patches/mutate6.py`): **10 eingebaute Fehler, alle gefangen** (verschiedene Personen statt Verträge gezählt, nur aktive
oder nur Verträge ohne Enddatum gezählt, Hinweis schon beim 5. Vertrag, Meldung wieder als „Grenze erreicht“, FAQ und Startseite wieder mit „Schüler“, FAQ ohne Zählregel, Rechnungsmeldung ohne „nichts gesperrt“
oder mit „unbegrenzt“). `ruff format --check` und `ruff check` über `backend/apps` und `backend/tutorflow` sind sauber.

Neu:

- `apps/core/tests/test_design_tokens.py` rechnet die Kontraste (WCAG 2.1 AA) **aus `tokens.css`** nach, in beiden Themen, und gleicht den Block „Gerät dunkel“ mit
  `data-theme="dark"` ab. Prüft, dass die Schriften als Datei vorhanden sind.
- `apps/core/tests/test_component_colours.py`: Regeln aus der Messung der gerenderten Farben (Ränder, Fokus, `--on-danger`), das Verhalten der mobilen Tabellen und
  ein Wächter gegen die bekannten zu schwachen festen Farbwerte in Seitenvorlagen.
- `apps/core/tests/test_icons.py`: nur bekannte Icon-Namen, **kein `{% icon %}` in einem Attribut**, `{% load icons %}` vorhanden, keine Emojis als Icons in Seitenvorlagen.
- `apps/core/tests/test_page_structure.py`: genau eine `<h1>` je öffentlicher Seite in DE und EN, Fakten der Startseite gegen den Code, Anrede, Anmeldeseiten.
- `apps/core/tests/test_free_tier_wording.py`: Wortlaut von Startseite, FAQ und Meldungen gegen die Konstanten (die Zahl gilt „Schülerverträgen“, nie „Schülern“); Zählregeln der Rechnungen (Monat, Storno, Status,
  Monatsgrenze in deutscher Zeit); Zählregeln der Verträge über den echten Anlegeweg: derselbe Mensch mit mehreren Verträgen zählt mehrfach, beendete (`end_date`) und inaktive Verträge zählen, Löschen senkt die Zahl,
  der Hinweis kommt beim 6. und nicht beim 5. Vertrag und bei jedem weiteren, gespeichert wird immer, deutscher und englischer Text.
- `apps/portal/test_portal_language.py`: Portal bleibt mit englischem Sprachcookie deutsch; die englische Start- und Anmeldeseite nennen es.
- `apps/core/tests/test_next_redirects.py`: `?next=` intern befolgt, fünf externe Schreibweisen abgelehnt (Tutor-Anmeldung, Portal-Anmeldung, Sprachwahl).
- `apps/core/tests/test_theme_shell.py`, `apps/students/test_delete_confirm.py`, `apps/lessons/tests/test_week_block_colours.py`, `apps/lessons/tests/test_reschedule_cancel_link.py`.
- `apps/core/tests/test_logo_cascade.py` (22.11.2026): Wächter für die Kaskade der Logo-Regeln am Stylesheet (Themen-Selektoren in `:where()`; die Regel, die den Schriftzug bis 1100 px ausblendet, schlägt jede Themen-Regel);
  mit der alten CSS-Datei fällt er durch.
- `scripts/browser/header-logo-regression.cjs` (22.11.2026): Browser-Matrix für die Kopfzeile (Logovariante, Sprachwahl, Navigation, Überlauf), siehe „Nachträgliche Korrektur“; danach um Escape im Mobilmenü sowie die Ausrichtung der
  Überschriften erweitert. Sie läuft nicht in der CI (sie braucht einen Browser); die Anleitung steht im Kopf der Datei.
- `apps/core/tests/test_mobile_nav.py`: Das Menü-Skript schließt das offene Menü bei Escape und gibt den Fokus zurück; im Mobilmenü stehen die Überschriften neben dem Symbol und der Pfeil am rechten Rand (Quelltext von `base.html`, `shell.css`).
- `apps/core/tests/test_review_prompt_i18n.py`: Hinweis, Knopf und Dialog des Bewertungsablaufs im Dashboard folgen der Sprache; die deutsche Oberfläche zeigt wörtlich die bisherigen Texte.
- Angepasst, weil sich Markup bewusst geändert hat (die Absicht der Tests bleibt): `test_contrast_tokens.py` (liest `tokens.css`),
  `test_calendar_site_texts.py` (Gruppen „Im Free-Tarif“, „Ab dem Pro-Tarif“; zusätzlich: Meetingräume und KI stehen nur dort), `test_faq_pages.py` (das Icon-Sprite ist kein
  Sprunglink), `test_i18n.py`, `test_week_view_click_behavior.py` (SVG statt Emoji), `portal/test_login_page.py`, `portal/test_week_picker.py`,
  `portal/tests_portal.py` (Meldung per `role="alert"`, Konto bleibt unaktiviert), `test_csp_nonce.py` (erkennt jetzt auch `javascript:` in Vorlagenausdrücken),
  `test_design_tokens.py` (Paar `on-danger`/`danger`).

## Prüfung in der laufenden Anwendung (Browser)

**Umgebung.** (`tools/…` steht hier für `/root/agents/tutorflow-redesign-tools/…`.) Der ai-server darf keinen Port öffnen (Portmonitor, auch nicht auf 127.0.0.1). Deshalb startet hier **kein Server**:

- Auf dem ai-server liest ein Relay-Prozess (`tools/relay.py`) HTTP-Anfragen als JSON-Zeilen von stdin und lässt sie durch den vollständigen Middleware-Stack der Anwendung
  laufen (Sitzungen, CSRF-Prüfung erzwungen, CSP-Header, WhiteNoise, Übersetzung, `DEBUG=False`). Er schreibt die Antworten nach stdout.
- Auf dem Mac steuert Playwright ein Chromium (Chrome for Testing) und leitet jede Anfrage an `http://localhost:8765/…` über eine SSH-Verbindung an den Relay weiter.
  Es lauscht nirgends ein Port auf dem Server. Cookies, Weiterleitungen, Formulare und JavaScript laufen wie im Browser; die CSP des Servers gilt im Browser.
- **Isolation:** eigene SQLite-Kopie mit Demodaten (`e2e.sqlite3`), Umgebung bereinigt (`env -i`, keine Zugangsdaten), jede Verbindung nach außen wird gesperrt und
  protokolliert, E-Mails landen im Speicher des Testlaufs und werden abgerufen statt versendet. LLM, Stripe, Kalenderabgleich und Push haben keine Schlüssel.
  Nur Testdaten (Konten `e2e_tutor`, `e2e_eltern`, `e2e_schueler`, Schüler „Berta“).

**Ergebnis des letzten Laufs: 81 Prüfungen, 0 fehlgeschlagen** (`node tools/mac/e2e.js`). Geprüft wurde:

| Bereich | Ablauf |
|---|---|
| Hinweisfenster „in aktiver Entwicklung“ | erscheint beim ersten Besuch je Tab, ist ein beschrifteter Dialog, Escape schließt es, im selben Tab kommt es nicht wieder (es fängt bis dahin Klicks ab, siehe Prüfgrenzen) |
| Anmeldung, Abmeldung | falsches Passwort zeigt die Meldung in „du“-Form; richtige Anmeldung führt ins Dashboard; Abmelden; danach ist `/students/` nicht mehr erreichbar |
| `?next=` | intern (`/students/`) wird befolgt; extern abgelehnt: `https://boese.example/…`, `//boese.example/…`, `/\boese.example`, `javascript:alert(1)` (Anmeldung); externes Ziel in der Sprachwahl; externes Ziel in der Portal-Anmeldung |
| Schüler | anlegen mit Formularfehlern (Eingabe bleibt erhalten), anlegen mit Bestätigung, bearbeiten, **Löschseite öffnen, Abbrechen (Schüler bleibt), tatsächlich löschen (Datensatz weg)** |
| Stunden | anlegen mit Bestätigung, bearbeiten, verschieben mit Fehler und Erfolg; **Abbrechen über die Seitenhistorie**, **Abbrechen ohne Historie** (echter Link), `?next=` erscheint in keinem Link |
| Wochenansicht | Woche vor und zurück, Datumssprung, Klick auf ein Zeitfeld öffnet den Anlege-Dialog, Monatsansicht |
| Portal | Eltern: Anmeldung, nur Dashboard und Hilfe in der Navigation, Überschrift „Deine Kinder“, Abmelden; Schüler: Dashboard, Kalender, Stunden, Hilfe, aktuelle Seite markiert; Seite bleibt mit englischem Sprachcookie deutsch (`lang="de"`, deutsches Hinweisfenster), keine Sprachwahl |
| Mobil (390 px) | Menü öffnet und schließt (Knopf, Klick daneben, `aria-expanded`); Themenwechsel schaltet um, `aria-pressed`, bleibt nach dem Neuladen; Sprachwechsel DE → EN → DE |
| Mobile Tabellen | Schülerliste: Aktionen sichtbar und `sticky`. Stundenliste: breiter als ihr Kasten, **nur die Tabelle scrollt, die Seite nicht**, Randschatten vorhanden, am Ende sind die ersten Spalten weggescrollt und die Aktionsspalte bleibt sichtbar |
| Abfang | Passwort-Zurücksetzen löst genau eine Mail aus, sie landet im Abfangspeicher (Empfänger Testadresse); kein Versuch einer Verbindung nach außen; sonst nichts verschickt |
| Konsole | keine Fehler außer dem blockierten eRecht24-Skript (siehe Prüfgrenzen), keine Verstöße gegen die CSP |

## Messung der tatsächlich gerenderten Farben

`tools/mac/contrast.js` misst im Browser die **berechneten** Stile (nicht die Token-Liste): jedes sichtbare Textelement gegen seinen wirksamen Hintergrund (Halbtransparenz über
alle Vorfahren verrechnet), Platzhalter, Ränder von Eingabefeldern (3:1) und die Fokus-Anzeige der ersten Tab-Stopps. Maßstab: Text 4,5:1, großer Text 3:1.

- Umfang: 35 Seitentypen (Startseite, Anmeldung, FAQ, Rechtstexte, Dashboard, Listen, Wochen- und Monatskalender, Stunden-, Vertrags- und Rechnungsdetails, Einstellungen, Portal, 404 …),
  hell und dunkel, Deutsch und Englisch, 1440 und 390 px; je Lauf rund 2500 Kombinationen.
- **Vorher:** 81 (hell) und 75 (dunkel) unter dem Grenzwert, Fokus-Anzeige in 3 Fällen unter 3:1. **Nachher:** 0 und 0, Fokus 0 von 208.
- Kalender: Wochenblöcke (geplant, gehalten, bezahlt, Sperrzeit, Konfliktmarke), Monatsansicht und Portalkalender wurden mitgemessen; zwei Fälle wurden behoben (weiße Schrift auf `--success`
  mit Abblenden; „Details“ im dunklen Monatskalender 4,09:1 → Hinterlegung zurückgenommen).
- Hinweise (`.message`, `.alert-*`), Formulare (Beschriftung, Eingabe, Platzhalter, Rand), Schaltflächen und Marken in beiden Themen: ohne Befund nach den Korrekturen.
- Textmarker (`.hl`) in beiden Themen: Tinte auf Gelb hell 9,95:1, dunkel 9,87:1.
- **Nicht bewertet** (Hintergrund ist ein Verlauf, 8 hell / 7 dunkel): der Kopfbereich der Startseite (liniertes Papier). Von Hand für den ungünstigsten Pixel der Linie gerechnet
  (hell `#e5e3db`, dunkel `#1a2526`): Tinte 11,6:1 / 13,6:1, `--ink-soft` 5,6:1 / 7,7:1, Akzent-Text 4,8:1 / 8,9:1; alle über 4,5:1.

## Regressionsvergleich der ausgenommenen Bereiche

`tools/compare_excluded.py` läuft im unveränderten Stand (`ce2ea1f`, eigener Klon ohne Remote) und im Zweig und vergleicht die Ausgaben:

| Bereich | Ergebnis |
|---|---|
| Meetingraum (`meeting/room.html`) | gleich, außer der Stunden-ID in zwei Adressen |
| Rechnungsdokument (erzeugte Datei) | gleich, außer der Rechnungsnummer (Datenbank-ID) |
| Rechnungs-PDF, Text DE und EN | gleich, außer der Rechnungsnummer |
| Einladung ins Portal (E-Mail, Text und HTML) | gleich |
| Passwort-Zurücksetzen (E-Mail, Text und HTML) | gleich, außer dem Nutzer-Kennzeichen im Link |

Dazu: Seit `ce2ea1f` hat sich keine E-Mail-Vorlage, kein PDF-Code und kein `room.html` geändert; die geänderte Vertragsbezeichnung kommt in keinem dieser Bereiche vor.

## Vorschau und Isolation (präzise)

*Stand 22.11.2026: Der Zweig ist veröffentlicht. Dieser Abschnitt beschreibt die Isolation der Vorschau-Phase davor; der Klon `/root/agents/tutorflow-redesign` hat weiterhin keinen Remote.*

**Was tatsächlich fehlt (Anbindung an das Deployment):** Der Klon `/root/agents/tutorflow-redesign` hat **keinen Remote** (`git remote` ist leer; `origin` wurde nach dem Klonen entfernt).
Von dort aus kann also nichts zu GitHub gepusht werden. Veröffentlicht wird Preceptly über GitHub-Actions und Railway nach einem Push des Hauptklons (`/root/bin/preceptly-push.sh`);
diesen Weg gibt es aus dem Klon nicht. Der Zweig `redesign/preview` existiert nur in diesem Klon.

**Das ist keine Garantie für spätere Bereitstellungsarten.** Es gibt keine technische Sperre in GitHub oder Railway gegen den Zweig. Wer einen Remote hinzufügt, den Zweig in den Hauptklon holt
(`git fetch`/`merge`), den Code kopiert oder einen Pull Request öffnet, hat danach den normalen Weg (CI, Railway). Auch ein Hinzufügen von Zugangsdaten zur Testumgebung hebt die Sperre auf.
Die Vorschau bleibt nur so isoliert, wie sie unten beschrieben ist.

**Lokale Bereitstellung** (die Werkzeuge liegen bewusst außerhalb des Repositorys: auf dem ai-server in `/root/agents/tutorflow-redesign-tools/`, der Mac-Teil dort unter `mac/`):

1. *Statische Spiegelung* (`render_site.py`, `render.sh`): Der Django-Testclient rendert 154 Seiten aus dem Zweig in Dateien; Screenshots und die Farbmessung lesen diese Dateien. Dabei läuft kein Server.
2. *Isolierte Anwendungsinstanz* (`relay.py`, `e2e.js`): siehe „Prüfung in der laufenden Anwendung“. Auch hier lauscht kein Port; die Isolation beruht auf der eigenen SQLite-Kopie, der bereinigten
   Umgebung (`env -i`), der Sperre ausgehender Verbindungen und dem Mail-Abfang.

**Nicht abgedeckt:** Daphne/ASGI-Schicht und WebSockets (Meetingraum in Echtzeit), PostgreSQL, Redis (Zwischenspeicher im Testlauf ist lokal), TLS/HSTS und die tatsächlich gesetzten Cookie-Merkmale
(`Secure` wird im Browser nachgebildet), die Railway-Umgebung (Proxy-Köpfe, Umgebungsvariablen), echter Mailversand, Stripe, KI-Server, Push, Kalenderabgleich, Datei-Uploads.

## Veröffentlichen und Zurücknehmen

**Stand 22.11.2026: veröffentlicht.** Andreas gab die Veröffentlichung von `0f4e7e2` ausdrücklich frei. `redesign/preview` wurde per Fast-Forward in `main` übernommen und um 14:10 UTC gepusht, Railway lieferte es um 14:24 UTC aus.
Danach fand die Live-Prüfung einen Fehler in der Kopfzeile im dunklen Thema; die Korrektur (Abschnitt „Nachträgliche Korrektur“) wurde als `2e7d597` veröffentlicht (CI grün, 17:17 UTC ausgeliefert, `commitHash` in Railway geprüft). Der Klon
`/root/agents/tutorflow-redesign` hat weiterhin keinen Remote; veröffentlicht wird aus dem Hauptklon `/root/agents/tutorflow`.

### Verlauf vom 22.11.2026 (UTC)

| Zeit | Schritt | Ergebnis |
|---|---|---|
| 13:55 | Vorab-Prüfung | `origin/main` = Hauptklon = `ce2ea1f`, Hauptklon sauber, Zweigspitze `0f4e7e2`, Pre-Push-Hook seit 18.06. unverändert |
| 13:55 | Zeitgrenze im Push-Skript | nur Zeile 8: `timeout 900 git push` → `timeout 1800 git push` (Hooks und Schutzprüfungen unverändert); Original: `/root/bin/preceptly-push.sh.bak-20261122-vor-timeout` |
| 13:56–14:10 | `git merge --ff-only`, dann `preceptly-push.sh` | Hook: `ruff check`, `compileall`, **1834 Tests OK (5 übersprungen) in 845 s**; Push `ce2ea1f..0f4e7e2` um 14:10 |
| 14:10–14:24 | GitHub Actions | Hygiene, Dependency Submission und CodeQL grün (14 s bis 2 min), **CI grün um 14:23:55 (13 min 6 s)** |
| 14:10:52–14:24:22 | Railway | Deployment `in_progress` ab 14:10:52, `success` um 14:24:22; Containerstart 14:24 UTC, „No migrations to apply“, danach keine Fehler und keine Neustarts im Protokoll |
| 14:24 | Ausgeliefert | `railway status --json` → `meta.commitHash` = `0f4e7e2f3f8fbfeb9dc9790e585bbdb0728072d3` (SUCCESS, Instanz RUNNING); GitHub-`main`, Hauptklon und Zweigspitze zeigen auf denselben Commit |

- **„Online“ reicht nicht als Nachweis.** In Railway ist kein Healthcheck konfiguriert (`healthcheckPath` leer); „Online“ heißt nur, dass der Container läuft. Die Version belegt `meta.commitHash`.
- **Abhängigkeit von der CI:** Die Railway-Einstellung „auf CI warten“ ist per CLI nicht lesbar (`railway status --json` enthält keinen passenden Schlüssel, `railway config pull` braucht das Railway-TypeScript-SDK). Der Zeitverlauf
  spricht dafür: Bei drei Commits stand das Deployment 22, 28 und 27 Sekunden nach dem CI-Ende auf `success`, obwohl es Sekunden nach dem Push auf `in_progress` ging. Belegt ist das Verhalten, nicht die Einstellung.
- **Zeitgrenze:** Der Hook brauchte 845 s. Die frühere Grenze von 900 s für `git push` samt Hook hätte kaum gereicht und bei Überschreitung nichts gepusht („TESTS FAILED - not pushed“).

### Live-Prüfung (so ausgeführt)

Passwörter gibt der Agent nicht in Anmeldeformulare der Produktion ein, auch nicht die öffentlichen Demo-Zugänge; Andreas meldete sich selbst im Browserfenster an.

- **Ohne Anmeldung (HTTP):** 11 Seiten 200, 404-Seite 404, je genau ein `<h1>`; neue Free-Texte vorhanden, alter Text fehlt; alle Stylesheets und beide Schriften 200; CSP mit `font-src 'self'` und Skript-Nonce; Sprachwechsel setzt
  `django_language`; ein externes `next` im Sprachwechsel (drei Schreibweisen) landet immer auf `https://preceptly.de/`; das Portal bleibt mit englischem Cookie deutsch; `/students/` ohne Sitzung leitet auf die Anmeldung mit `next` um.
- **Ohne Anmeldung (frischer Browserkontext, 36 Prüfungen, 0 Fehler):** Themenwechsel bleibt nach dem Neuladen, Sprachwechsel DE/EN/DE, alle öffentlichen Seiten ohne Konsolenfehler und CSP-Verstöße, mobil kein Überlauf, Menü öffnet und schließt.
- **Angemeldet (Demo-Konto, Business):** Dashboard, Themenwechsel, Sprachwechsel DE/EN/DE, Wochenansicht mit „Nächste Woche“, Monatskalender, Schülerliste, Löschseite (öffnet; „Abbrechen“ lässt alle vier Schüler stehen), „Termin verschieben“ mit
  „Abbrechen“, `?next=` (extern → Dashboard, intern wird befolgt), mobil 390 px (Menü, Stundenliste: nur die Tabelle scrollt, Aktionen bleiben sichtbar).
- **Portal-Anmeldung** hell und dunkel; **eRecht24:** Skript und Modal-Dateien geladen, Element vom Widget ergänzt, keine CSP-Meldung (der Button wurde nicht bedient).
- **Nicht geprüft:** angemeldeter Portalbereich (kein Portal-Konto, Einladungen sind in der Demo gesperrt), Anlegen und Löschen von Datensätzen in der Produktion, Anmeldung mit `?next=` über das Formular, andere Browser als Chromium.

### Nachträgliche Korrektur: Kopfzeile im dunklen Thema (22.11.2026)

**Befund (Live-Prüfung):** Bei dunkler Geräteeinstellung zeigte die Kopfzeile bis 1100 px Breite Schriftzug **und** Icon. Auf öffentlichen Seiten kam bei 360 und 390 px das Home-Symbol hinzu: Sprachwahl und Anmelden-Symbol ragten aus dem Fenster, die
Seite scrollte seitlich (bei 390 px rechte Kante der Sprachwahl bei 431 px). Hell und ab 1101 px war alles in Ordnung.

**Ursache:** CSS-Spezifität. `shell.css` blendet den Schriftzug bis 1100 px mit `nav .nav-brand .logo-full { display: none }` aus (0,2,1). Im Block `@media (prefers-color-scheme: dark)` setzte
`:root:not([data-theme="light"]) .logo--on-dark { display: block }` (0,3,0, `components.css`) ihn wieder ein. Die Bedingung `:not([data-theme="light"])` trifft auch dann, wenn das Seitenskript `data-theme="dark"` gesetzt hat, deshalb trat der Fehler
mit und ohne gespeicherte Themenwahl auf. Der Fall „Thema ausdrücklich dunkel auf heller Geräteeinstellung“ blieb heil, weil `[data-theme="dark"] .logo--on-dark` (0,2,0) verliert.

**Korrektur:** In `components.css` stehen die Themen-Selektoren der Logo-Fassung jetzt in `:where()` (Spezifität 0,1,0, wie `.logo--on-dark`). Sie wählen nur noch die Fassung und überstimmen keine Layout-Regel; unter gleicher Spezifität entscheidet die Reihenfolge
(dunkle Fassung zuletzt, im Kommentar vermerkt). Es gibt keine zusätzliche überschreibende Sonderregel, `shell.css` ist unverändert.

**Prüfung:**

| Prüfung | Ergebnis |
|---|---|
| Browser-Matrix `scripts/browser/header-logo-regression.cjs` gegen die **fehlerhafte Live-Seite** (`/login/`) | 1004 Prüfungen, **86 Verstöße in 6 von 16 Fällen**: Gerät dunkel ohne gespeicherte Wahl und mit gespeichert dunkel (je de/en) sowie ohne JavaScript; alle hellen Fälle und „Gerät dunkel, gespeichert hell“ bestanden |
| dieselbe Matrix gegen die Spiegelung des korrigierten Stands (`/login/`, `/`, `/dashboard/`) | 3012 Prüfungen, **0 Verstöße in 48 Fällen** (öffentliche und angemeldete Kopfzeile; 360, 390, 768, 1099, 1100, 1101, 1440 px; Gerät hell/dunkel × gespeichert keins/hell/dunkel × de/en, dazu ohne JS) |
| Wächter `apps/core/tests/test_logo_cascade.py` (5 Tests) | besteht; **mit der alten CSS-Datei schlägt er fehl** (5 Fehlschläge, 1 Fehler) |
| verwandte Tests (`test_logo_cascade`, `test_component_colours`, `test_theme_shell`, `test_design_tokens`, `test_icons`) | 46 Tests OK |

Die Matrix prüft je Fall: Thema im Dokument, genau die vorgesehene Logovariante in der Marke (bis 1100 px nur das Icon, ab 1101 px nur der Schriftzug in der Fassung des wirksamen Themas), Menüknopf nur bis 1100 px, Themenknopf, Konto-Symbole und Sprachwahl vollständig im
Fenster, Navigation erreichbar (bis 1100 px nach dem Öffnen der Schublade, deren Logo ebenfalls zum Thema passt; das Menü schließt wieder) und keinen seitlichen Überlauf.

**Warum es vorher nicht auffiel:** Die Vorab-Prüfungen maßen Kontraste und den Überlauf der Seiten, aber nicht, welche Logovariante je Breite sichtbar ist, und sie setzten das Thema immer ausdrücklich. Die Kombination „dunkle Geräteeinstellung + schmaler Bildschirm + keine gespeicherte
Themenwahl“ kam nirgends vor. Seitdem gibt es die Matrix (Browser) und den Wächter (Stylesheet, läuft im Test-Lauf der CI).

### Ablauf für künftige Veröffentlichungen (so bewährt)

0. Vorab: `git -C /root/agents/tutorflow ls-remote origin main` zeigt den erwarteten Stand, `git -C /root/agents/tutorflow status --short` ist sauber. Ist `main` weitergelaufen (zum Beispiel durch Dependabot), zuerst
   `bash /root/agents/tutorflow-redesign-tools/publish_rehearsal.sh` und das Ergebnis neu bewerten (das Skript legt den Wegwerf-Klon `/root/agents/tutorflow-publish-check` bei Bedarf aus dem Hauptklon neu an; er hat keinen Remote
   und wurde am 22.11.2026 nach der Veröffentlichung gelöscht).
1. Zweig übernehmen: `cd /root/agents/tutorflow && git fetch /root/agents/tutorflow-redesign redesign/preview && git merge --ff-only FETCH_HEAD`; `git rev-parse HEAD` muss die vorgesehene Commit-Nummer zeigen. Bewusst **kein** `--no-ff`.
2. `bash /root/bin/preceptly-push.sh` (die Zeitgrenze steht jetzt auf 1800 s; Hook rund 14 Minuten, danach CI rund 14 Minuten, Deployment unter 1 Minute). Fortschritt in `/tmp/pd.log`. Von außen sichtbar: `gh run list --commit <Hash>`.
3. Nachweis des ausgelieferten Commits: `railway status --json` → `meta.commitHash` des aktiven Deployments, nicht „Online“.
4. Live-Prüfung wie oben; zusätzlich `node scripts/browser/header-logo-regression.cjs --base https://preceptly.de --paths /login/` in einem frischen Browserkontext (Anleitung im Kopf der Datei).

### Zurücknehmen

- **Schnell (Railway):** Im Dashboard beim Dienst `preceptly` unter *Deployments* das Deployment des vorigen Commits wieder ausspielen. Das wurde nicht ausprobiert.
- **Über Git (im Probelauf bis auf den Baum nachgestellt):**
  ```
  cd /root/agents/tutorflow
  git revert --no-commit <Basis>..<Spitze>
  git commit -m "revert: <Beschreibung>"
  bash /root/bin/preceptly-push.sh
  ```
  Für das Redesign ist `<Basis>` = `ce2ea1f`. Danach laufen Hook, CI und Railway wie oben (30 bis 35 Minuten). Es gibt keine Migration und keine Datenbankänderung. Der Service Worker legt `/static/` „cache first“ ab, aber die Dateinamen tragen einen
  Hash, und HTML kommt immer zuerst aus dem Netz: Nach Deployment oder Rücknahme gibt es keine veralteten Stylesheets.

### Auffälligkeiten der Live-Prüfung

**Behoben** (im Commit, der diesen Abschnitt enthält):

- **Escape im Mobilmenü:** Escape schloss nur die Dropdowns, nicht das offene Mobilmenü. Jetzt schließt Escape das Menü und setzt den Fokus auf den Menüknopf (`base.html`, im vorhandenen Menü-Skript).
- **Überschriften im Mobilmenü:** Die aufklappbaren Bereiche standen zentriert, die Links linksbündig. `justify-content: space-between` verteilte Symbol, Beschriftung und Pfeil auf drei Kinder. Jetzt steht die Beschriftung
  neben dem Symbol und der Pfeil per `margin-left: auto` am rechten Rand (`shell.css`, die bestehende Regel wurde geändert, es gibt keine Zusatzregel).
- **Bewertungsablauf im Dashboard:** Hinweis, Knopf und Dialog (sechs Texte) hatten deutsche Quelltexte mit leerer Übersetzung und blieben in der englischen Oberfläche deutsch. Jetzt sind die Quelltexte englisch wie im übrigen Projekt, und die
  deutsche Oberfläche zeigt wörtlich die bisherigen Texte (`dashboard.html`, `django.po`).

**Prüfung:** Die neuen Tests (`test_mobile_nav.py`, `test_review_prompt_i18n.py`) schlagen auf dem Stand davor fehl und bestehen danach; zusammen mit den verwandten Tests 108 Tests OK. Die erweiterte Browser-Matrix meldete live vor der
Korrektur (`/login/`) 1244 Prüfungen mit 180 Verstößen in 12 von 16 Fällen (je 60 bei Ausrichtung, Escape-Schließen und Fokus-Rückgabe; die vier Fälle ohne JavaScript haben keine Schublade) und gegen die Spiegelung des korrigierten Stands
(`/login/`, `/`, `/dashboard/`) 3732 Prüfungen ohne Verstoß in 48 Fällen.

**Weiterhin offen (kein Fehler der Anwendung oder nicht Teil der Korrektur):**

- Der Sprunglink des eRecht24-Widgets überdeckt bei Tastaturfokus kurz das Logo. Das ist das Verhalten des Drittanbieter-Skripts und wird nicht verändert.
- Einzelne Antworten der Anmeldeseiten brauchten kurz nach dem Deployment 1,8 bis 2,6 s (sonst unter 1,1 s); keine Fehler im Protokoll, kein Vergleichswert. Eine Beobachtung, kein Fehler.
- Weitere deutsche Festtexte im Dashboard-Quelltext (zum Beispiel das `aria-label` der Stundentabelle) sind nicht Teil dieser Korrektur und wurden nicht geändert.

### Wesentliche Risiken

- **Alle Nutzer sehen die neue Oberfläche auf einmal** (Tutor-App und Portal). Es gibt keine stufenweise Freigabe.
- **Nur Chromium geprüft.** Safari, Firefox, echte Handys und Screenreader nicht.
- **Umgebung der Produktion nicht nachgebildet** (PostgreSQL, Daphne mit WebSockets, TLS, Railway-Proxy). Die Änderung berührt sie nicht; Befunde zeigen sich erst live.
- **Das Portal ist nur deutsch** (bewusst); wer mit englischem Sprachcookie ins Portal kommt, bekommt Deutsch.

## Verbleibende Prüfgrenzen

- Vor der Veröffentlichung gab es keine Produktion und keine Staging-Umgebung; geprüft wurde gegen Demodaten in der lokalen Datenbank. Nach der Veröffentlichung wurde live geprüft (Abschnitt „Veröffentlichen und Zurücknehmen“).
- **Nur Chromium** (Chrome for Testing). Safari, Firefox, echte Handys, Screenreader und die Tastaturbedienung außerhalb der gemessenen Tab-Stopps wurden nicht geprüft. Seitliches Scrollen einer
  Tabelle per Tastatur hängt vom Browser ab: Die Seite macht den Scrollbereich nicht selbst fokussierbar (kein `tabindex`), und das Verhalten der Browser dafür wurde nicht geprüft.
- **eRecht24-Widerrufsbutton:** Das Skript `widerrufsbutton-cdn.e-recht24.de` wird in jeder Seite der Tutor-App geladen. Es wurde in allen Läufen **blockiert** und blieb damit eine **ungeprüfte externe
  Integration**: Weder sein Verhalten noch sein Aussehen, noch die Wirkung der neuen CSP/Stile darauf wurden getestet. Die Einbindung und alle rechtlichen Inhalte sind unverändert. **Nachtrag 22.11.2026:** Live geprüft: Skript und Modal-Dateien wurden geladen, das Widget hat das Element ergänzt, es gab keine CSP-Meldung; bedient wurde der Button nicht. Das Stylesheet
  zielt nur mit `#eRecht24RevocationButton` auf den Knopf (Umriss in der Fußzeile).
- Das Hinweisfenster „in aktiver Entwicklung“ erscheint beim ersten Aufruf je Tab (auch im Portal) und fängt Klicks ab, bis man es schließt. Das ist **bestehendes Verhalten**, nicht Teil
  dieses Auftrags und unverändert.
- Mobile Tabellen: Die Randschatten und der sticky-Rand zeigen weitere Spalten; wer gar nicht scrollt, sieht bei schmalen Bildschirmen angeschnittene Spaltenköpfe. Ein Umbau zu Karten ist nicht erfolgt (entschieden).
- Der Meetingraum, die E-Mail-Vorlagen und die PDF-Rechnung sind **nicht** neu gestaltet (entschieden); der Meetingraum hat Emojis in den Schaltflächen.
- Das Portal ist deutsch fest verdrahtet (kein `{% trans %}`); **es gibt keine englische Portalfassung** und sie ist nicht Teil dieses Auftrags. Das Portal erzwingt Deutsch, hat keine Sprachwahl,
  und die englischen Seiten sagen es.
- Nicht im Browser bedient wurden: Registrierung, Rechnungserstellung, Datei-Uploads, Zahlungen, Meetings, Kalender-Anbindung. Sie sind durch die Test-Suite abgedeckt, nicht durch die Browserläufe.
- Tabellen mit sehr vielen Spalten und Zellen mit langem Inhalt wurden nur in den Listen von Schülern und Stunden im Browser geprüft.

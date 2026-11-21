# Designsystem „Kladde“: Überarbeitung von Gestaltung, Texten und Technik

**Stand:** 21.11.2026 · Auftrag von Andreas: Preceptly „gestalterisch, inhaltlich und technisch“ vollständig überarbeiten.
**Nicht veröffentlicht, nicht gemergt, nicht gepusht.** Der Stand liegt auf dem Zweig `redesign/preview` in der Arbeitskopie `/root/agents/tutorflow-redesign`.
**Abschließender Stand:** Der oberste Commit des Zweigs (`git log -1 redesign/preview`) enthält dieses Dokument. Der Commit mit dem gesamten Code davor ist
`6832107` (enthält Code, Übersetzungen und Tests). Test-Suite auf diesem Code: 1824 Tests, alle bestanden (5 übersprungen).

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
| **Free-Tarif:** „Free“ und die Zahlen 5 Schüler / 8 Rechnungen passen, sofern sie dem tatsächlichen Verhalten entsprechen | Das tatsächliche Verhalten wurde im Code geprüft (nächster Abschnitt). Es ist ein **Hinweis, keine Sperre**; der Wortlaut sagt deshalb „Gedacht für bis zu 5 Schüler / 8 Rechnungen im Monat“ und nennt Auslöser und Zählregeln. „Free“ steht jetzt überall in der Oberfläche (Startseite, FAQ, Einstellungen, Meldungen, Demo-Zugang). Technische Tarifkennungen (`free`), Zahlungszuordnungen und Vertragsbedingungen sind unverändert |
| **Ansprache im Portal:** durchgehend „du“, auch gegenüber Eltern; Rechtstexte und verbindliche Dokumente unverändert | „Deine Kinder“, „mit deinem Konto“ im Elternportal; „Was möchtest du löschen?“; Meldung an Tutoren in `students/views.py`. **Unverändert** bleiben: Rechtstexte, Abo-Bestätigung und Widerruf (`core/email/subscription_confirmation.txt`, `revocation_confirm.html`, `views_erecht24_revocation.py`), die Zahlungsaufforderung im PDF (`pdf_service.py`), die Datenschutz-Overrides (`legal_overrides.py`) und Meldungen für Betreiber (`ai/client.py`, Verwaltungsbefehle). Die „Sie“ in der Portal-FAQ meinen „sie (Mehrzahl)“ |
| **Mobile Tabellen:** seitlich scrollbar genügt; nur der Tabellenbereich scrollt, Aktionen bleiben erreichbar, weitere Spalten erkennbar | Bis 820 px wird die Tabelle selbst zum Scrollbereich (`overflow-x: auto`, `overscroll-behavior-x: contain`), die Seite scrollt nicht mit. Schatten an den Rändern zeigen verborgene Spalten. Bis 640 px bleibt die letzte Spalte mit den Aktionen (Details, Bearbeiten, Löschen) rechts stehen (`position: sticky`), die Knöpfe stehen untereinander und halten die Spalte schmal. Browserprüfung am 390-px-Viewport: siehe unten |
| **Ausgenommene Bereiche:** Meetingraum, E-Mail-Vorlagen, PDF-Rechnung nicht neu gestalten; Regressionen durch gemeinsame Styles prüfen | Alle drei bringen ihr eigenes Gerüst mit und laden **keines** der neuen Stylesheets. Geprüft durch Dateivergleich (keine Änderung seit `ce2ea1f`) und durch einen Renderlauf im unveränderten und im neuen Stand (Abschnitt „Regressionsvergleich“): kein Unterschied außer Datenbank-Kennungen |
| **Portal nur Deutsch:** englische Portalübersetzung außerhalb des Auftrags; keine Sprachwahl darf eine englische Fassung versprechen | Das Portal hat keine Sprachwahl. Neue Middleware `apps/portal/language.py` stellt alle Adressen unter `/portal/` auf Deutsch (vorher bekam man mit englischem Sprachcookie eine Mischung, weil das Hinweisfenster der Basis übersetzbar ist). Die englische Start- und Anmeldeseite sagen: „The portal is currently available in German only.“ |

## Free-Tarif: was tatsächlich gezählt wird

Geprüft in `apps/core/free_limits.py`, `apps/billing/views.py`, `apps/core/feature_flags.py`, PRD und den bestehenden Tests; abgesichert durch
`apps/core/tests/test_free_tier_wording.py`.

- **Es sind weiche Grenzen.** Beim 6. Schüler und bei der 9. Rechnung eines Kalendermonats erscheint ein Hinweis mit Link zu den Preisen. Gespeichert wird trotzdem, es wird
  nichts gesperrt. (Meine Aussage vom 20.11., die Grenzen würden „durchgesetzt“, war ungenau.)
- **Gilt nur für Free-Konten, die ab dem 02.07.2026 (12:00 UTC) angelegt wurden.** Ältere Free-Konten und alle bezahlten Tarife bekommen keinen Hinweis.
- **Schüler:** Es zählt jeder Vertrag des Kontos, auch beendete oder inaktive. Die Meldung sagte früher „aktive Schüler“; das stimmte nicht und ist korrigiert.
  Der Hinweis erscheint über „Schüler anlegen“ und über „Vertrag anlegen“.
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

Neu:

- `apps/core/tests/test_design_tokens.py` rechnet die Kontraste (WCAG 2.1 AA) **aus `tokens.css`** nach, in beiden Themen, und gleicht den Block „Gerät dunkel“ mit
  `data-theme="dark"` ab. Prüft, dass die Schriften als Datei vorhanden sind.
- `apps/core/tests/test_component_colours.py`: Regeln aus der Messung der gerenderten Farben (Ränder, Fokus, `--on-danger`), das Verhalten der mobilen Tabellen und
  ein Wächter gegen die bekannten zu schwachen festen Farbwerte in Seitenvorlagen.
- `apps/core/tests/test_icons.py`: nur bekannte Icon-Namen, **kein `{% icon %}` in einem Attribut**, `{% load icons %}` vorhanden, keine Emojis als Icons in Seitenvorlagen.
- `apps/core/tests/test_page_structure.py`: genau eine `<h1>` je öffentlicher Seite in DE und EN, Fakten der Startseite gegen den Code, Anrede, Anmeldeseiten.
- `apps/core/tests/test_free_tier_wording.py`: Wortlaut von Startseite, FAQ und Meldungen gegen die Konstanten; Zählregeln der Rechnungen (Monat, Storno, Status, Monatsgrenze in
  deutscher Zeit) und der Schüler (auch beendete).
- `apps/portal/test_portal_language.py`: Portal bleibt mit englischem Sprachcookie deutsch; die englische Start- und Anmeldeseite nennen es.
- `apps/core/tests/test_next_redirects.py`: `?next=` intern befolgt, fünf externe Schreibweisen abgelehnt (Tutor-Anmeldung, Portal-Anmeldung, Sprachwahl).
- `apps/core/tests/test_theme_shell.py`, `apps/students/test_delete_confirm.py`, `apps/lessons/tests/test_week_block_colours.py`, `apps/lessons/tests/test_reschedule_cancel_link.py`.
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

**Veröffentlichen** (erst nach ausdrücklicher Freigabe von Andreas):

1. Zweig prüfen: `git log main..redesign/preview`, volle Test-Suite, CI.
2. Auf dem ai-server in `/root/agents/tutorflow`: `git fetch /root/agents/tutorflow-redesign redesign/preview && git merge --no-ff FETCH_HEAD` (oder als Pull Request).
3. `bash /root/bin/preceptly-push.sh` (wartet auf CI und Railway). Railway deployt erst bei grünem CI.
4. Danach live prüfen: Startseite, Anmeldung, Dashboard, Wochenansicht, Portal-Login (auch mit englischem Sprachcookie), 404, jeweils hell und dunkel, DE und EN.

**Zurücknehmen:** `git revert -m 1 <Merge-Commit>` und erneut pushen. Es gibt **keine Datenbankänderung** und keine Migration; die neuen Dateien (Stylesheets,
Schriften, `apps/portal/language.py`) liegen nur im Code, die Middleware steht in `tutorflow/settings.py`. Der Service Worker (`sw.js`) legt `/static/` „cache first“ ab, aber die Dateinamen
tragen einen Hash (Manifest-Speicher): Nach Deploy oder Zurücknehmen gibt es keine veralteten Stylesheets, HTML kommt immer zuerst aus dem Netz.

## Verbleibende Prüfgrenzen

- Es gab keine Produktion und keine Staging-Umgebung; geprüft wurde gegen Demodaten in der lokalen Datenbank.
- **Nur Chromium** (Chrome for Testing). Safari, Firefox, echte Handys, Screenreader und die Tastaturbedienung außerhalb der gemessenen Tab-Stopps wurden nicht geprüft. Seitliches Scrollen einer
  Tabelle per Tastatur hängt vom Browser ab: Die Seite macht den Scrollbereich nicht selbst fokussierbar (kein `tabindex`), und das Verhalten der Browser dafür wurde nicht geprüft.
- **eRecht24-Widerrufsbutton:** Das Skript `widerrufsbutton-cdn.e-recht24.de` wird in jeder Seite der Tutor-App geladen. Es wurde in allen Läufen **blockiert** und blieb damit eine **ungeprüfte externe
  Integration**: Weder sein Verhalten noch sein Aussehen, noch die Wirkung der neuen CSP/Stile darauf wurden getestet. Die Einbindung und alle rechtlichen Inhalte sind unverändert. Das Stylesheet
  zielt nur mit `#eRecht24RevocationButton` auf den Knopf (Umriss in der Fußzeile).
- Das Hinweisfenster „in aktiver Entwicklung“ erscheint beim ersten Aufruf je Tab (auch im Portal) und fängt Klicks ab, bis man es schließt. Das ist **bestehendes Verhalten**, nicht Teil
  dieses Auftrags und unverändert.
- Mobile Tabellen: Die Randschatten und der sticky-Rand zeigen weitere Spalten; wer gar nicht scrollt, sieht bei schmalen Bildschirmen angeschnittene Spaltenköpfe. Ein Umbau zu Karten ist nicht erfolgt (entschieden).
- Der Meetingraum, die E-Mail-Vorlagen und die PDF-Rechnung sind **nicht** neu gestaltet (entschieden); der Meetingraum hat Emojis in den Schaltflächen.
- Das Portal ist deutsch fest verdrahtet (kein `{% trans %}`); **es gibt keine englische Portalfassung** und sie ist nicht Teil dieses Auftrags. Das Portal erzwingt Deutsch, hat keine Sprachwahl,
  und die englischen Seiten sagen es.
- Nicht im Browser bedient wurden: Registrierung, Rechnungserstellung, Datei-Uploads, Zahlungen, Meetings, Kalender-Anbindung. Sie sind durch die Test-Suite abgedeckt, nicht durch die Browserläufe.
- Tabellen mit sehr vielen Spalten und Zellen mit langem Inhalt wurden nur in den Listen von Schülern und Stunden im Browser geprüft.

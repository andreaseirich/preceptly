# Listen: Seitenwechsel, Sortierung und Filter

**Stand:** 18.11.2026 · Meldung von Andreas: „Es werden nicht alle Schüler in der Tabelle angezeigt.“ Gewünscht: Jede Tabelle erhält
alle Daten; gibt es mehr Einträge als eine Seite fasst, muss man zur nächsten Seite wechseln können; außerdem filtern und sortieren.

## Ursache

Fünf Listen schnitten mit `paginate_by` ab (Schüler, Verträge, Serien, Rechnungen je 20, Stunden 50), aber **keine einzige Vorlage**
hatte ein Bedienelement zum Weiterblättern (`page_obj`, `is_paginated` und `paginator` kamen in keinem Template vor). Ab dem 21.
Eintrag war der Rest nicht erreichbar. Im Betrieb betraf das ein Konto mit 28 Schülern (8 unsichtbar) und 299 Stunden (249
unsichtbar); die Rechnungen standen bei 19 von 20. Sortierung gab es nirgends (die Schülerliste hatte nicht einmal eine feste
Reihenfolge), gefiltert wurde nur nach Rechnungsstatus (Pro), Ausgabenjahr und, ohne Eingabefeld, nach Datum bei den Stunden.

Weitere Stellen, die still abschnitten:

| Stelle | Vorher | Jetzt |
|---|---|---|
| Dashboard „Anstehend“ (7 Tage) | `qs[:10]`, ohne Hinweis | alle Stunden der nächsten 7 Tage |
| Vertragsdetail, Fortschrittsnotizen | die letzten 10, ohne Hinweis | alle |
| Elternportal, Stunden des Kindes | die ersten 20, kein Weg weiter | Seiten zu je 20, `?page=` |
| Elternportal, Fortschrittsnotizen | die letzten 10, ohne Hinweis | alle |
| Ausgaben | ohne `year` alle Jahre in der Liste, die Summe darunter nur das laufende Jahr | ohne Angabe das laufende Jahr, Liste und Summe stimmen überein |

## Baukasten

Eine Mischklasse und drei Vorlagen-Tags statt einzelner Lösungen. Jede Liste beschreibt nur ihre Spalten und Filter.

| Teil | Aufgabe | Ort |
|---|---|---|
| `SortFilterListMixin` | Sortierung, Filter, tolerante Seitenzahl; greift erst in `paginate_queryset()` ein | `apps/core/list_mixin.py` |
| `SearchFilter`, `ChoiceFilter`, `DateFilter` | prüfen ihren Wert selbst, ungültige Werte gelten als nicht gesetzt | `apps/core/list_filters.py` |
| `{% sort_header %}`, `{% pagination %}`, `{% filter_bar %}` | Spaltenkopf mit `aria-sort`, Seitenwechsel, GET-Formular | `apps/core/templatetags/list_tools.py` und `templates/core/list_tools/` |
| `student_choices`, `institute_choices` | Auswahllisten, immer nur die eigenen Daten | `apps/contracts/list_helpers.py` |
| Gestaltung | Farben aus `base.html`, hell und dunkel | `apps/core/static/core/list-tools.css` |

Regeln, die der Baukasten durchsetzt:

- **Besitzer zuerst:** Die Ansicht beschränkt ihre Abfrage in `get_queryset()` wie bisher auf den Nutzer. Filter und Sortierung wirken
  erst danach (in `paginate_queryset()`) und können nie fremde Daten sichtbar machen.
- **Sortierschlüssel nur aus einer festen Liste** (`sort_options`). Ein Wert aus der Adresszeile gelangt nie in `order_by`.
  Unbekannte Schlüssel oder Richtungen gelten als nicht gesetzt.
- **Gleiche Werte bleiben stabil:** Am Ende sortiert immer `pk`, sonst könnte ein Eintrag auf zwei Seiten stehen und ein anderer auf
  keiner. Leere Werte (zum Beispiel ein Vertrag ohne Enddatum) stehen in beide Richtungen am Ende. Text wird ohne Beachtung der
  Groß-/Kleinschreibung sortiert.
- **Die Standardrichtung gilt nur für die Standardspalte.** Rechnungen und Stunden zeigen das Neueste zuerst; wählt man eine andere
  Spalte ohne Richtung, ist es aufsteigend. (Das fiel im ersten Testlauf auf.)
- **Tolerante Seitenzahl:** `?page=abc` führt auf Seite 1, `?page=999` auf die letzte Seite, nie zu 404.
- **Filter bleiben beim Blättern und Sortieren erhalten**, eine neue Sortierung beginnt auf Seite 1.
- **Barrierefreiheit:** Das Filterformular trägt `role="search"`, jedes Feld ein Label; die aktive Spalte `aria-sort`; die aktuelle
  Seite `aria-current="page"`; der Seitenwechsel ist ein `div role="navigation"` mit Beschriftung (kein `<nav>`: `base.html` stylt jedes
  `nav` als dunkle Menüleiste). Klickflächen sind mindestens 40 px hoch.
- Unter jeder Liste steht „Einträge 21–40 von 45“, damit man sieht, dass nichts fehlt.

## Die Listen

| Liste | Sortierbar nach | Filter | Seite |
|---|---|---|---|
| Schüler (`contracts:list`) | Schüler, Institut, Satz, Dauer, Von, Bis, Status | Suche (Name, Schule, Institut), Status, Institut (auch „Privatunterricht“) | 20 |
| Schüler (`students:list`) | Name, Schule, Klasse | Suche | 20 |
| Rechnungen | ID, Zahler, Zeitraum, Betrag, Status, Erstellt | Suche (Zahler, Nummer); **Status nur im Pro-Tarif, wie bisher** | 20 |
| Stunden | Datum, Uhrzeit, Dauer, Schüler, Status | Suche, Schüler, Status, Von/Bis (Datum) | 50 |
| Serien | Schüler, Uhrzeit, Start, Status | Suche, Schüler, Status (aktiv, beendet, inaktiv) | 20 |
| Ausgaben | Datum, Kategorie, Beschreibung, Betrag | Jahr, Kategorie, Suche | 20 |

## Entscheidungen

- **Schülerliste:** Standard ist jetzt Nachname A–Z (vorher unsortiert, faktisch „zuletzt begonnen zuerst“).
- **Ausgaben:** Ohne Jahr gilt das laufende Jahr (die Seite behauptete das schon: Auswahl und Summe). Die Summe unter der Liste gilt für die
  gefilterte Liste über alle Seiten und heißt „Gesamtausgaben (gefiltert)“, sobald Kategorie oder Suche wirken. Sie rechnet mit dem
  **wirksamen** Betrag (Betriebsanteil), wie die Steuerseiten. Vorher stand dort die Summe der Rohbeträge, bei einer nur zu 50 % betrieblichen
  Ausgabe zeigte die Zeile also 5 €, die Summe zählte 10 €.
- **Rechnungsstatus-Filter** bleibt ein Pro-Merkmal. Neu für alle sind Suche und Sortierung.

## Absichtlich begrenzt (und beschriftet)

- Vertragsdetail: „Im Portal abgesagte Termine“ zeigt die letzten 20, der Text sagt das.
- Portal-Startseite des Schülers: „Nächste Stunden“ und „Letzte Stunden“ (je 5) sind Vorschauen mit dem Knopf „Alle Stunden“.
- Berichte: Bestenlisten („Top 5“) sind als solche benannt.
- Nicht angefasst: Institute (kleine Liste, nicht begrenzt), Verwaltungsseiten (Statistik, Bewertungen), Monats- und Wochenansichten.

## Geprüft

- Neue Tests (`apps/core/tests/test_list_tools.py`, `apps/portal/test_parent_detail_pages.py`): je Liste jede Seite erreichbar, kein Eintrag
  doppelt oder fehlend (auch bei lauter gleichen Sortierwerten), Sortierung in beide Richtungen, Schlüssel-Einschleusung, Filter,
  fremde Daten bleiben draußen, Eingaben maskiert, Beschriftung der Felder.
- **Mutationstest:** 23 Fehler gezielt in den neuen Code eingebaut (Sortierschlüssel ungeprüft, Tie-Breaker weg, leere Werte nicht am Ende, Auswahl ungeprüft, strenge Seitenzahl, Filter gehen beim Blättern verloren, Standardjahr weg, Summe falsch, Abschneiden wieder da, Statusfilter für alle, Suchtext nicht maskiert, Label am falschen Feld, Portal nur Seite 1 u. a.). Alle 23 werden von den Tests bemerkt. Im ersten Durchlauf überlebte einer: Ohne `pk` als letztes Sortierkriterium fiel kein Test auf, denn in einer Testtransaktion ordnet PostgreSQL gleiche Werte zufällig stabil. Deshalb prüft jetzt ein Test die Abfrage selbst (letztes Sortierkriterium jeder Liste und Spalte ist `pk`). Ein weiterer Fehler wurde zunächst übersprungen, weil Ruff die Zeile umformatiert hatte, und danach nachgeholt.
- Alle vorhandenen Tests der betroffenen Seiten laufen unverändert (106), darunter die Abfragezahl-Tests der Rechnungsliste und des
  Dashboards (die Zahl der Abfragen wächst nicht mit den Daten).
- Seiten mit Beispieldaten im Browser angesehen (hell und dunkel). Dabei fiel auf, dass der Seitenwechsel als `<nav>` in der dunklen
  Menüleisten-Gestaltung erschien; behoben.

## Offen

- Das Elternportal zeigt die Stunden des Kindes in Seiten, filtert und sortiert aber nicht (nur ein Kind, überschaubar).
- Die Tabellen sind auf dem Handy unverändert breit; das Filterformular bricht dort um.

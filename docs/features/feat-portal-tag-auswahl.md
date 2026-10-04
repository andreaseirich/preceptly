# Portal: Tag-Auswahl beim Buchen und Verschieben

**Stand:** 04.10.2026 · Auftrag von Andreas („Ändere und verbessere es“), ausgelöst durch die Rückmeldung einer
Mutter: Sie sehe nur die bereits belegten Termine und könne keinen freien anklicken. Später klappte es am Computer,
vermutlich war es vorher am Handy schwierig.

## Was vorher störte

- Das stündliche Wochenraster zeichnete nur „Belegt“ ein, **freie Zeiten waren nirgends zu sehen**.
- Die Tage waren unscheinbar gestylte Spaltenköpfe, nichts deutete darauf hin, dass man sie antippen kann. Der
  einzige Hinweis war eine kleine graue Zeile.
- Die Tabelle war mindestens 640 px breit: am Handy seitliches Scrollen, Freitag bis Sonntag waren verdeckt.

## Verhalten jetzt

Auf der Seite „Termin buchen“ und „Termin verschieben“ ist jeder Tag der Woche eine große Schaltfläche mit
Wochentag, Datum und der Zahl der freien Zeiten („9 freie Zeiten“, „1 freie Zeit“, „nichts frei“, vergangene Tage
„vorbei“). Tage mit freien Zeiten sind grün hinterlegt, der gewählte Tag ist voll eingefärbt.

- **Handy:** Die Tage stehen untereinander (Zeile je Tag), kein seitliches Scrollen. Darüber Zeitraum und
  „Vorige Woche“ / „Nächste Woche“ nebeneinander.
- **Ab 760 px Breite:** sieben Spalten nebeneinander.
- Antippen eines Tages füllt das Datum, lädt darunter die freien Uhrzeiten und scrollt dorthin (bei
  „Bewegung reduzieren“ ohne Animation). Wer das Datum im Feld darunter wählt, sieht den Tag oben ebenfalls markiert.
- Ist in der ganzen Woche nichts mehr frei, steht dort ein Hinweis auf „Nächste Woche“.
- Unter dem (noch deaktivierten) Knopf steht, was fehlt: „Wähle zuerst einen Tag und eine Uhrzeit …“.
- Uhrzeit-Schaltflächen sind mindestens 44 px hoch.

## Woher die Zahl kommt

Aus derselben Regel wie die Liste darunter (`_get_available_slots` mit Dauer und Fahrzeit des Vertrags,
Arbeitszeiten, belegten Zeiten, Blockzeiten, Mindestabstand). Zahl und Liste können nicht auseinanderlaufen (Test:
`test_the_count_always_matches_the_list_below`). Eine gemeinsame `BusyCalendar` für die ganze Woche: höchstens drei
Abfragen mehr, nicht sieben mal drei.

Das stündliche Raster mit „Belegt“ ist auf diesen Seiten entfallen. Der Fehler, für den es damals eine Regression
gab (eine Stunde mitten in einer Blockzeit sah frei aus), ist weiter abgedeckt: Zeiten, die eine Blockzeit
berühren, zählen nie als frei (`test_week_calendar_multihour.py`). Die Wochenansicht im Kalender des Portals
(`PortalWeekView`) ist unverändert.

## Barrierefreiheit (WCAG 2.1 AA)

Schaltflächen mit `aria-pressed`, Liste mit `role="list"`, sichtbarer Fokus (`:focus-visible`), Kontraste mit den
Portal-Variablen für Hell und Dunkel geprüft (Vorschau in beiden Modi), Zustand nie nur durch Farbe (Text mit
Zahl), Zielgröße ≥ 44 px, keine Inline-Handler (CSP), Reflow bis 320 px ohne seitliches Scrollen. Die Liste der
Uhrzeiten hat `aria-live="polite"`, auch beim Verschieben.

## Code

| Teil | Ort |
|---|---|
| Tag-Auswahl (Markup, Skript) | `apps/portal/templates/portal/_week_calendar_widget.html` |
| Stylesheet | `apps/core/static/css/week-picker.css` |
| Freie Zeiten je Tag | `_free_slots_for_week`, `_build_week_calendar(with_free_slots=True)` in `apps/portal/views.py` |
| Seiten | `portal/book.html`, `portal/reschedule.html` |
| Tests | `apps/portal/test_week_picker.py`, `apps/portal/test_week_calendar_multihour.py` |

## Bekannt, nicht geändert

Die Liste der freien Zeiten blendet für **heute** bereits vergangene Uhrzeiten nicht aus, und die Buchung lehnt nur
vergangene *Tage* ab, nicht vergangene Zeiten am heutigen Tag. Das war schon vorher so.

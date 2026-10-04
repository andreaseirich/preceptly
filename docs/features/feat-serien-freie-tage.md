# Portal-Serien: nur freie Tage buchen

**Stand:** 04.10.2026 (erweitert am selben Tag: Serien des Tutors, Arbeitszeiten) · Auftrag von Andreas: „Serientermine sollen nur für die Tage gebucht werden, die
frei sind. Alle Termine sollen gebucht werden, nur die Tage, die nicht frei sind, sollen ausgelassen
werden.“

## Verhalten

Legt eine Familie im Portal eine Serie an (ab dem Pro-Tarif), bucht Preceptly jeden Tag der Serie, an dem der
Tutor zu dieser Zeit frei ist, und lässt alle anderen aus. Danach steht in zwei Meldungen:

- „Serientermin erstellt. 3 Termine gebucht.“
- „1 Tag war schon belegt und wurde ausgelassen: 12.10.2026.“ (bis zu 10 Tage, dann „und N weitere“)

Die Meldung nennt nur das Datum, nicht, was dort steht: Familien sehen im Portal sonst auch nur „Belegt“.

**Sind alle Tage belegt,** wird keine Serie angelegt. Die Familie bekommt eine Warnung und landet wieder auf
dem Formular, um eine andere Uhrzeit oder andere Wochentage zu wählen.

## Was „frei“ heißt

Dieselbe Regel wie bei der Einzelbuchung (`apps/lessons/availability.py`). Eine Zeit ist **belegt**, wenn

- der Tutor dort eine andere Stunde hat (geplant, unterrichtet oder bezahlt, bei irgendeinem Schüler), oder
- dort eine Blockzeit liegt (auch mehrtägige, etwa Urlaub, an jedem Tag davon).

Nicht belegt sind abgesagte Stunden, Stunden anderer Tutoren und Zeiten, die nur aneinandergrenzen (eine Stunde
endet genau, wenn die nächste beginnt). Der Vertragsumfang wird nicht geprüft.

## Arbeitszeiten (nur Portal)

Familien können im Portal nur innerhalb der Standard-Arbeitszeiten des Tutors (`UserProfile.default_working_hours`)
buchen. Das galt bisher nur für die Liste der freien Zeiten, jetzt auch beim Speichern:

| Wo | Was passiert außerhalb der Arbeitszeiten |
|---|---|
| Einzelbuchung | Wird verweigert („Diese Zeit liegt außerhalb der Arbeitszeiten deines Tutors.“) |
| Verschieben | Wie die Buchung |
| Serie | Der Tag wird ausgelassen und in einer eigenen Meldung genannt („3 Tage liegen außerhalb der Arbeitszeiten …“). Liegt jeder Tag außerhalb oder ist belegt, wird keine Serie angelegt |

Die ganze Stunde muss in einem Zeitfenster liegen (ohne Fahrzeit); sie kann nicht über zwei Fenster reichen. Ein Tag
ohne Fenster (etwa Sonntag) zählt als außerhalb. **Sind gar keine Arbeitszeiten eingetragen,** gibt es keine
Einschränkung beim Speichern (Serien und direkte Buchungen laufen wie bisher), die Liste der freien Zeiten bleibt
dann aber leer, Familien sehen dort also nichts zum Anklicken.

Der Tutor selbst ist nicht an seine Arbeitszeiten gebunden und darf auch außerhalb planen.

Eine Stunde desselben Schülers zur selben Zeit zählt als „gibt es schon“ und nicht als belegt.

## Serien des Tutors

Seit 04.10.2026 (Antwort von Andreas: „Ja“) gilt die Regel auch für Serien, die der Tutor selbst anlegt: Wiederholung
im Stundenformular, Serienformular, Bearbeiten einer Serie (Stunden werden neu erzeugt) und „Termine generieren“.
Belegte Tage (andere Stunde, Blockzeit, Mindestabstand) werden ausgelassen und in einer Meldung genannt
(„1 Tag war schon belegt und wurde ausgelassen: 12.10.2026.“), alle anderen gebucht. Anders als im Portal bleibt eine
Serie auch dann bestehen, wenn kein Tag frei war, und „Termine generieren“ füllt später frei gewordene Tage auf.

**Nicht angefasst:** Das Ändern einer ganzen Serie über eine einzelne Stunde (`views_crud.py`, „alle zukünftigen
Stunden“) bleibt „alles oder nichts“ und macht bei Konflikten alle Änderungen rückgängig. Dort gibt es keine
ausgelassenen Tage.

## Code

| Teil | Ort |
|---|---|
| Regel „frei“, belegte Zeiten für einen Zeitraum in zwei Abfragen | `apps/lessons/availability.py` (`BusyCalendar`) |
| Serienerzeugung mit `skip_busy` (und `within_hours` fürs Portal), Ergebnis `busy` mit Grund | `apps/lessons/recurring_service.py` |
| Arbeitszeiten (`OFF_HOURS`, `working_windows`, `enforce_working_hours`) | `apps/lessons/availability.py` |
| Meldung beim Tutor | `apps/lessons/series_messages.py`, benutzt in `recurring_views.py` und `views_crud.py` |
| Portal: Serie anlegen, Meldungen | `PortalRecurringCreateView`, `_busy_days_message` in `apps/portal/views.py` |
| Freie Zeiten und Einzelbuchung nutzen dieselbe Regel | `_get_busy_slots`, `_get_available_slots` |
| Tests | `apps/portal/test_series_skip_busy.py`, `apps/lessons/test_working_hours.py` |

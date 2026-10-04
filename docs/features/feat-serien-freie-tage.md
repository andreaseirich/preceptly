# Portal-Serien: nur freie Tage buchen

**Stand:** 04.10.2026 · Auftrag von Andreas: „Serientermine sollen nur für die Tage gebucht werden, die
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
endet genau, wenn die nächste beginnt). **Nicht geprüft** werden die Arbeitszeiten des Tutors und der
Vertragsumfang; die Einzelbuchung prüft beim Speichern ebenfalls nur belegte Zeiten.

Eine Stunde desselben Schülers zur selben Zeit zählt als „gibt es schon“ und nicht als belegt.

## Was sich nicht ändert

Serien, die der Tutor selbst anlegt (Stundenformular, Serienformular, „Termine generieren“), verhalten sich wie
bisher: Sie legen alle Termine an und markieren Konflikte. Der Schalter `skip_busy` der Serienerzeugung ist
standardmäßig aus.

## Code

| Teil | Ort |
|---|---|
| Regel „frei“, belegte Zeiten für einen Zeitraum in zwei Abfragen | `apps/lessons/availability.py` (`BusyCalendar`) |
| Serienerzeugung mit `skip_busy`, Ergebnis `busy` | `apps/lessons/recurring_service.py` |
| Portal: Serie anlegen, Meldungen | `PortalRecurringCreateView`, `_busy_days_message` in `apps/portal/views.py` |
| Freie Zeiten und Einzelbuchung nutzen dieselbe Regel | `_get_busy_slots`, `_get_available_slots` |
| Tests | `apps/portal/test_series_skip_busy.py` |

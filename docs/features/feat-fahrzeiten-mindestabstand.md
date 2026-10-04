# Fahrzeiten je Schüler und Mindestabstand zwischen Terminen

**Stand:** 04.10.2026 · Auftrag von Andreas: Standard-Fahrzeiten je Schüler, die je Stunde änderbar sind, und
ein Mindestabstand zwischen Terminen, auch zwischen Stunde und Blockzeit, „damit es nicht zu stressig wird“.

## Standard-Fahrzeiten je Schüler

Der Vertrag trägt `default_travel_time_before_minutes` und `default_travel_time_after_minutes` (0 bis 480,
leer heißt 0). Sie stehen im Vertragsformular und auf der Vertragsseite.

- **Neue Stunde oder Serie (Tutor):** Das Formular füllt die Fahrzeitfelder mit den Werten des gewählten Schülers.
  Wechselt der Tutor den Schüler, füllt `static/js/travel-defaults.js` sie neu, es sei denn, er hat eine Fahrzeit
  selbst geändert. Er kann sie für jede Stunde ändern. Beim Bearbeiten und nach einem Fehler im Formular passiert
  nichts.
- **Portal:** Einzelbuchungen und Serien, die Familien anlegen, übernehmen die Standardwerte.
- **Bestehende Stunden** bleiben, wie sie sind. Jede Stunde behält ihre Werte, auch wenn der Vertrag sich ändert.

## Mindestabstand

Einstellung des Tutors: `UserProfile.min_gap_minutes` (0 bis 240, 0 = keiner), unter Einstellungen →
„Mindestabstand zwischen Terminen“. Zwischen dem Ende eines Termins samt Fahrzeit danach und dem Beginn des
nächsten samt Fahrzeit davor liegen mindestens so viele Minuten, zwischen Stunde und Blockzeit ebenso.

| Wo | Was passiert |
|---|---|
| Stunden, die der Tutor selbst einträgt | Nicht verweigert, aber als Konflikt mit `too_close` markiert („Zu wenig Abstand“, Meldung mit den Minuten) |
| Freie Zeiten im Portal | Zeiten, die Abstand oder Fahrzeit unterschreiten, werden nicht angeboten |
| Einzelbuchung im Portal | Wird beim Speichern verweigert |
| Verschieben im Portal | Wie die Buchung, mit der eigenen Fahrzeit der Stunde. Prüft jetzt auch Blockzeiten |
| Serien im Portal | Tage, die den Abstand unterschreiten, werden ausgelassen |

## Was sich im Portal zusätzlich ändert

Die Fahrzeiten **vorhandener** Stunden zählen jetzt als belegt. Vorher belegte im Portal nur die Stunde selbst
Zeit, die Fahrzeit nicht, die Konflikterkennung beim Tutor rechnete sie aber schon mit. Familien können also
nicht mehr in die Fahrzeit einer anderen Stunde buchen.

## Code

| Teil | Ort |
|---|---|
| Regel „frei“ (Fahrzeit, Abstand, Blockzeiten) | `apps/lessons/availability.py` (`BusyCalendar`) |
| Mindestabstand eines Tutors | `apps/lessons/spacing.py` |
| Konflikte beim Tutor | `apps/lessons/conflict_service.py` (`too_close`, `gap_minutes`) |
| Vorbelegung der Fahrzeiten | `apps/lessons/travel_defaults.py`, `apps/core/static/js/travel-defaults.js` |
| Portal | `_get_available_slots`, `_busy_error`, Buchung, Verschieben, Serie in `apps/portal/views.py` |
| Tests | `apps/lessons/test_travel_defaults.py`, `apps/lessons/test_min_gap.py` |

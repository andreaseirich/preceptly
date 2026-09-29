# Stunden: wann und von wem gebucht

**Stand:** 29.09.2026 · Anlass: Ein Schüler bestritt eine Portal-Buchung vom
07.09.2026. Welches Konto sie angelegt hatte, ließ sich nicht mehr feststellen.

## Verhalten

- **Jede neue Stunde** speichert das buchende Konto (`Session.booked_by`) und
  den Weg (`Session.created_via`: `portal_booking`, `portal_series`, `tutor`).
- **Serien** speichern beides ebenfalls, ihre Stunden übernehmen es. Verlängert
  der Tutor später eine Serie aus dem Portal, gelten die neuen Stunden weiter
  als vom Portal-Konto gebucht: Maßgeblich ist, wer die Serie angelegt hat.
- **Anzeige** auf der Detailseite, Zeile „Gebucht“:
  - Tutor: „07.09.2026, 21:35 · über das Portal vom Schülerkonto (E-Mail)“,
    eigene Buchungen als „von dir“.
  - Portal: ohne E-Mail (Geschwister könnten mitlesen), das eigene Konto als
    „von dir“, der Tutor mit Namen. Immer auf Deutsch, auch bei englischem
    Browser.
- **Ältere Stunden** zeigen nur den Zeitpunkt und bei Einzelbuchungen im Portal
  den Weg, dazu den Hinweis, dass das Konto erst seit 29.09.2026 gespeichert
  wird. Nachgetragen wird nichts, weil sich das Konto nicht sicher ableiten
  lässt.
- **Verschieben** ändert die Angabe nicht.
- **Buchungslimit:** Portal-Serien zählen weiterhin nicht zum monatlichen
  Limit, denn das zählt nur `portal_booking`.

## Nebenbei behoben

Legte der Tutor eine Serie über das normale Stundenformular an, entstand am
ersten Serientag zusätzlich eine doppelte Einzelstunde: `super().form_valid()`
speicherte das Formular ein zweites Mal. In der Produktion kam das bis
29.09.2026 nicht vor (geprüft).

## Code

| Teil | Ort |
|---|---|
| Felder | `Session.booked_by`, `RecurringSession.booked_by` und `created_via`, Migration `lessons/0019_booked_by` |
| Anzeige | `apps/lessons/booking_origin.py` |
| Setzen | Portal: `PortalBookingView`, `PortalRecurringCreateView`; Tutor: `LessonCreateView`, `RecurringLessonCreateView`; Serien: `RecurringSessionService._create_session_if_not_exists` |
| Tests | `apps/lessons/test_booking_origin.py` |

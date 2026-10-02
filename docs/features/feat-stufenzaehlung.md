# Stufenvergütung: Zählweise und Startwert

**Stand:** 02.10.2026 · Anlass: TutorSpace zahlte ab dem 30.09.2026 schon 15 €/h,
Preceptly rechnete noch mit 14 €/h. Entschieden von Andreas am 02.10.2026.

## Warum

Preceptly zählte für die Stufen kumulierte Minuten: 60 Minuten = 1 Stunde.
TutorSpace zählt Einheiten: Jede angefangene Stunde eines Termins zählt als 1.
Ein Termin mit 30 Minuten bringt dort also eine ganze Einheit, in Preceptly nur
eine halbe Stunde. Mit jedem kurzen Termin lief der Zähler weiter auseinander.

## Verhalten

Jedes Institut hat zwei neue Einstellungen (Institute → Bearbeiten):

| Einstellung | Bedeutung |
|---|---|
| Zählweise | „Nach Dauer (60 Minuten = 1)“ ist der Standard und das bisherige Verhalten. „Nach Einheit (angefangene Stunde = 1)“ zählt 30 und 60 Minuten als 1, 120 Minuten als 2. |
| Startwert | Stunden oder Einheiten, die das Institut schon gezählt hat, bevor die erfassten Stunden beginnen. Wird zum Zähler addiert. |

- **Bezahlt wird immer nach Dauer.** 30 Minuten bringen den halben Stundensatz.
  Die Zählweise bestimmt nur, wann die nächste Stufe gilt.
- **Ein langer Termin über die Schwelle** wird je angefangener Stunde mit dem
  Satz dieser Einheit bezahlt: Bei 120 Minuten kann die erste Stunde noch den
  alten und die zweite schon den neuen Satz haben.
- **Der Zählbeginn** („nur zählen ab“) und der Ausschluss von Tutor-Ausfällen
  gelten in beiden Zählweisen.
- **Fortschrittsanzeige und Rechnungsvorschau** nutzen dieselbe Zählung wie
  die Abrechnung. Bis 02.10.2026 zählte die Fortschrittsanzeige auch
  Tutor-Ausfälle mit, die Abrechnung nicht.
- **Rechnungen, die es schon gibt,** ändern sich nicht. Neu berechnet werden
  nur Stunden, die noch auf keiner Rechnung stehen.

## TutorSpace (Konto von Andreas)

Zählweise „Nach Einheit“, Startwert 5. Vor dem 30.09.2026 zählte Preceptly 145
Einheiten seit dem Zählbeginn 12.01.2026. Mit dem Startwert ist die Stunde am
30.09.2026 um 16:00 Uhr die 151. Einheit und damit die erste mit 15 €/h. Woher
die Differenz von 5 kommt, ist offen; Andreas hat den Stichtag vorgegeben.

## Code

| Teil | Ort |
|---|---|
| Zählweise und Pool | `apps/contracts/tier_counting.py` |
| Felder | `Institute.tier_count_mode`, `Institute.tier_count_offset`, Migration `contracts/0021_tier_count_mode` |
| Abrechnung | `institute_billing.calculate_tiered_amount` |
| Fortschritt | `services.get_institute_tier_progress` |
| Rechnungsvorschau | `billing/views.py` (`tutorspace_preview_prior_units`) |
| Tests | `apps/contracts/test_tier_counting.py` |

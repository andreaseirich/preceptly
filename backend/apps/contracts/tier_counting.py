"""Wie ein Institut Stunden für die Stufenvergütung zählt.

Zwei Zählweisen (Institute.tier_count_mode):

- COUNT_BY_DURATION: nach Dauer, 60 Minuten = 1 Stunde. Standard.
- COUNT_BY_STARTED_HOUR: nach Einheit, jede angefangene Stunde eines Termins
  zählt als 1 (30 Minuten = 1, 60 = 1, 120 = 2). So zählt z. B. TutorSpace.

Bezahlt wird in beiden Fällen nach Dauer. Die Zählweise bestimmt nur, wann die
nächste Stufe erreicht ist. Institute.tier_count_offset ist der Startwert: was
das Institut schon gezählt hat, bevor die hier erfassten Stunden beginnen.
"""

from decimal import Decimal

COUNT_BY_DURATION = "duration"
COUNT_BY_STARTED_HOUR = "started_hours"


def started_hours(duration_minutes) -> int:
    """Angefangene Stunden eines Termins: 30 -> 1, 60 -> 1, 61 -> 2, 120 -> 2."""
    return -(-max(0, int(duration_minutes or 0)) // 60)


def counted_total(durations, mode: str, offset: int = 0) -> Decimal:
    """Zählerstand in Stunden (nach Dauer) bzw. Einheiten, einschließlich Startwert."""
    if mode == COUNT_BY_STARTED_HOUR:
        return Decimal(sum(started_hours(d) for d in durations) + offset)
    return Decimal(sum(int(d or 0) for d in durations)) / Decimal("60") + offset


def tier_pool(institute):
    """Stunden, die für die Stufen zählen: unterrichtet oder bezahlt, kein
    Tutor-Ausfall, ab dem Zählbeginn des Instituts."""
    from apps.lessons.models import Session  # lokaler Import gegen Zirkelbezug

    qs = Session.objects.filter(
        contract__user=institute.user,
        contract__institute_fk=institute,
        status__in=["taught", "paid"],
        tutor_no_show=False,
    )
    if institute.tier_count_from is not None:
        qs = qs.filter(date__gte=institute.tier_count_from)
    return qs

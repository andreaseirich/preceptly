"""
TutorSpace compensation rules (Gehalt) based on cumulative taught hours.

Rules (cumulative across **all** TutorSpace contracts of the same tutor, in chronological order;
optional profile ``tutorspace_tier_count_from`` limits which lesson dates enter the pool):
- Hours 1..50:   13 €/h
- Hours 51..150: 14 €/h
- Hours 151..450: 15 €/h
- Hours 451..1000: 16 €/h
- Hour 1001+:    17 €/h

The calculation is done in minutes to correctly handle non-60-minute sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.contracts.institute_utils import TUTORSPACE_INSTITUTE_NAME, is_tutorspace_institute
from apps.core.models import UserProfile
from django.contrib.auth.models import User


@dataclass(frozen=True)
class TutorSpaceTier:
    start_hour_inclusive: int  # 1-based hour index
    rate_eur_per_hour: Decimal


TIERS: list[TutorSpaceTier] = [
    TutorSpaceTier(start_hour_inclusive=1, rate_eur_per_hour=Decimal("13")),
    TutorSpaceTier(start_hour_inclusive=51, rate_eur_per_hour=Decimal("14")),
    TutorSpaceTier(start_hour_inclusive=151, rate_eur_per_hour=Decimal("15")),
    TutorSpaceTier(start_hour_inclusive=451, rate_eur_per_hour=Decimal("16")),
    TutorSpaceTier(start_hour_inclusive=1001, rate_eur_per_hour=Decimal("17")),
]


def tutorspace_rate_for_hour_index(hour_index_1_based: int) -> Decimal:
    """
    Map hour number (1-based, i.e. the 51st hour counts) to the hourly rate in EUR.
    """
    if hour_index_1_based <= 0:
        raise ValueError("hour_index_1_based must be >= 1")
    current = TIERS[0].rate_eur_per_hour
    for tier in TIERS:
        if hour_index_1_based >= tier.start_hour_inclusive:
            current = tier.rate_eur_per_hour
        else:
            break
    return current


def _tier_boundaries_minutes() -> list[int]:
    # Convert start_hour (1-based) to start-minute index (0-based).
    # Example: hour 51 starts after 50*60 minutes.
    boundaries = []
    for tier in TIERS[1:]:
        boundaries.append((tier.start_hour_inclusive - 1) * 60)
    return boundaries


def tutorspace_rate_for_cumulative_minute(cumulative_minute_0_based: int) -> Decimal:
    """
    Given the count of already taught minutes BEFORE the minute we are about to pay for,
    return the hourly rate for that next minute.
    """
    if cumulative_minute_0_based < 0:
        cumulative_minute_0_based = 0
    # hour_index_1_based for the next minute:
    # minutes 0..59 => hour 1, minutes 60..119 => hour 2, ...
    hour_index = (cumulative_minute_0_based // 60) + 1
    return tutorspace_rate_for_hour_index(hour_index)


def _tutorspace_session_precedes_in_tier_order(a, b) -> bool:
    """
    True if session a counts before b in the global TutorSpace tier timeline.

    Order: (date, start_time, created_at, pk). Using created_at avoids relying only on pk
    when several lessons share the same clock slot (e.g. backfilled or two pupils same time).
    """
    if a.date != b.date:
        return a.date < b.date
    if a.start_time != b.start_time:
        return a.start_time < b.start_time
    ca = getattr(a, "created_at", None)
    cb = getattr(b, "created_at", None)
    if ca is not None and cb is not None and ca != cb:
        return ca < cb
    if ca is not None and cb is None:
        return True
    if ca is None and cb is not None:
        return False
    ap = getattr(a, "pk", None) or 0
    bp = getattr(b, "pk", None) or 0
    return ap < bp


def _tutorspace_minutes_before_session(session, tutor: User) -> int:
    """
    Sum duration_minutes of TutorSpace sessions (taught/paid, tutor_no_show=False) strictly
    before ``session`` in tier order.

    Note: a tutor_no_show session is not in this queryset but still gets a correct total from
    rows that precede it in time order.

    If the tutor's profile has ``tutorspace_tier_count_from`` set, only sessions on or after
    that date participate in the tier pool (earlier TutorSpace lessons are ignored for tiers).
    """
    from apps.lessons.models import Session  # local import to avoid circulars

    profile = UserProfile.objects.filter(user=tutor).first()
    tier_from = getattr(profile, "tutorspace_tier_count_from", None) if profile else None

    qs = Session.objects.filter(
        contract__student__user=tutor,
        contract__institute__iexact=TUTORSPACE_INSTITUTE_NAME,
        status__in=["taught", "paid"],
        tutor_no_show=False,
    )
    if tier_from is not None:
        qs = qs.filter(date__gte=tier_from)
    qs = qs.order_by("date", "start_time", "created_at", "pk").only(
        "id", "date", "start_time", "duration_minutes", "created_at"
    )

    total = 0
    for row in qs:
        if _tutorspace_session_precedes_in_tier_order(row, session):
            total += int(row.duration_minutes or 0)
    return total


def calculate_tutorspace_amount_for_session(session, tutor: User) -> Decimal:
    """
    Calculate the TutorSpace compensation amount for one session.

    - Uses cumulative minutes from all TutorSpace sessions (taught/paid) of the tutor,
      excluding tutor_no_show for tier progression, in order (date, start_time, created_at, pk).
    - Splits the session duration across tier boundaries when needed.
    """
    if not session or not tutor:
        return Decimal("0.00")
    contract = getattr(session, "contract", None)
    if not contract or not is_tutorspace_institute(getattr(contract, "institute", None)):
        raise ValueError("Session is not a TutorSpace session")

    minutes_before = _tutorspace_minutes_before_session(session, tutor)
    duration = int(getattr(session, "duration_minutes", 0) or 0)
    if duration <= 0:
        return Decimal("0.00")

    boundaries = _tier_boundaries_minutes()
    amount = Decimal("0.00")
    remaining = duration
    cursor = minutes_before

    def next_boundary_after(minute_index: int) -> int | None:
        for b in boundaries:
            if b > minute_index:
                return b
        return None

    while remaining > 0:
        rate = tutorspace_rate_for_cumulative_minute(cursor)
        nb = next_boundary_after(cursor)
        chunk = remaining if nb is None else min(remaining, nb - cursor)
        amount += (Decimal(chunk) / Decimal("60")) * rate
        cursor += chunk
        remaining -= chunk

    if getattr(session, "tutor_no_show", False):
        profile = UserProfile.objects.filter(user=tutor).first()
        pct = int(getattr(profile, "tutor_no_show_pay_percent", 0) or 0) if profile else 0
        pct = max(0, min(100, pct))
        base = amount
        if pct >= 100:
            pass  # full TutorSpace amount despite flag
        else:
            # Retain pct% of usual pay; remainder is not paid; additionally deduct the usual
            # amount so net = base * pct/100 - base (e.g. 0% → -base, 50% → -base/2).
            amount = base * (Decimal(pct) / Decimal("100")) - base

    return amount.quantize(Decimal("0.01"))

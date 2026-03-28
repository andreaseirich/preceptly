"""
TutorSpace compensation rules (Gehalt) based on cumulative taught hours.

Rules (global across all TutorSpace contracts of the same tutor):
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

from apps.core.models import UserProfile
from django.contrib.auth.models import User
from django.db.models import Q, Sum

TUTORSPACE_INSTITUTE_NAME = "TutorSpace"


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


def is_tutorspace_institute(institute: str | None) -> bool:
    return (institute or "").strip().lower() == TUTORSPACE_INSTITUTE_NAME.lower()


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


def calculate_tutorspace_amount_for_session(session, tutor: User) -> Decimal:
    """
    Calculate the TutorSpace compensation amount for one session.

    - Uses cumulative minutes from all TutorSpace sessions (status taught/paid) of tutor.
    - Orders by (date, start_time, id) and counts only sessions strictly before this one.
    - Splits the session duration across tier boundaries when needed.
    """
    from apps.lessons.models import Session  # local import to avoid circulars

    if not session or not tutor:
        return Decimal("0.00")
    contract = getattr(session, "contract", None)
    if not contract or not is_tutorspace_institute(getattr(contract, "institute", None)):
        raise ValueError("Session is not a TutorSpace session")

    # sum duration_minutes for all TutorSpace sessions before this one
    before_q = Q(date__lt=session.date) | Q(date=session.date, start_time__lt=session.start_time)
    if getattr(session, "id", None):
        before_q |= Q(date=session.date, start_time=session.start_time, id__lt=session.id)

    # Tutor no-show (student waited): does not advance cumulative tier for later sessions.
    minutes_before = (
        Session.objects.filter(
            contract__student__user=tutor,
            contract__institute__iexact=TUTORSPACE_INSTITUTE_NAME,
            status__in=["taught", "paid"],
            tutor_no_show=False,
        )
        .filter(before_q)
        .aggregate(total=Sum("duration_minutes"))
        .get("total")
        or 0
    )
    minutes_before = int(minutes_before)
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
        amount = amount * (Decimal(pct) / Decimal("100"))

    return amount.quantize(Decimal("0.01"))

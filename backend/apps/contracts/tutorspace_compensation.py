"""
Generic tiered-compensation math (cumulative taught minutes -> hourly rate), shared by
apps.contracts.institute_billing for any institute with tiered pay configured.

The calculation is done in minutes to correctly handle non-60-minute sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth.models import User


@dataclass(frozen=True)
class TutorSpaceTier:
    start_hour_inclusive: int  # 1-based hour index
    rate_eur_per_hour: Decimal


def rate_for_hour_index(tiers: list[TutorSpaceTier], hour_index_1_based: int) -> Decimal:
    """
    Map hour number (1-based, i.e. the 51st hour counts) to the hourly rate in EUR,
    for an arbitrary (sorted) tier list.
    """
    if hour_index_1_based <= 0:
        raise ValueError("hour_index_1_based must be >= 1")
    current = tiers[0].rate_eur_per_hour
    for tier in tiers:
        if hour_index_1_based >= tier.start_hour_inclusive:
            current = tier.rate_eur_per_hour
        else:
            break
    return current


def tier_boundaries_minutes(tiers: list[TutorSpaceTier]) -> list[int]:
    # Convert start_hour (1-based) to start-minute index (0-based).
    # Example: hour 51 starts after 50*60 minutes.
    return [(tier.start_hour_inclusive - 1) * 60 for tier in tiers[1:]]


def rate_for_cumulative_minute(
    tiers: list[TutorSpaceTier], cumulative_minute_0_based: int
) -> Decimal:
    """
    Given the count of already taught minutes BEFORE the minute we are about to pay for,
    return the hourly rate for that next minute, for an arbitrary (sorted) tier list.
    """
    if cumulative_minute_0_based < 0:
        cumulative_minute_0_based = 0
    # hour_index_1_based for the next minute:
    # minutes 0..59 => hour 1, minutes 60..119 => hour 2, ...
    hour_index = (cumulative_minute_0_based // 60) + 1
    return rate_for_hour_index(tiers, hour_index)


def _session_precedes_in_tier_order(a, b) -> bool:
    """
    True if session a counts before b in the global tier timeline.

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


def minutes_before_session_for_institute(session, tutor: User, institute, tier_from) -> int:
    """
    Sum duration_minutes of sessions of ``institute`` (taught/paid, tutor_no_show=False)
    strictly before ``session`` in tier order.

    Note: a tutor_no_show session is not in this queryset but still gets a correct total from
    rows that precede it in time order.

    If ``tier_from`` is set, only sessions on or after that date participate in the tier pool.
    """
    from apps.lessons.models import Session  # local import to avoid circulars

    qs = Session.objects.filter(
        contract__user=tutor,
        contract__institute_fk=institute,
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
        if _session_precedes_in_tier_order(row, session):
            total += int(row.duration_minutes or 0)
    return total

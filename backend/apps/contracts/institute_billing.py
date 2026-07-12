"""
Per-institute billing rules: tiered compensation and tutor-no-show handling.

Every Institute a tutor creates is fully self-describing (tiers, no-show rule, tier
start date, no-show pay share) — Contract.institute_fk points to it, or is null for
private lessons. There is no name-based special-casing here: any institute gets
tiered pay and/or the no-show rule purely from its own stored configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth.models import User

from apps.contracts.tutorspace_compensation import (
    TutorSpaceTier,
    minutes_before_session_for_institute,
    rate_for_cumulative_minute,
    tier_boundaries_minutes,
)


@dataclass(frozen=True)
class InstituteBillingConfig:
    tiers: list[TutorSpaceTier] | None
    unpaid_on_tutor_no_show: bool
    tier_count_from: "date | None" = None  # noqa: F821 - forward ref, avoids top-level import
    tutor_no_show_pay_percent: int = 0


def _tiers_from_json(raw_tiers: list[dict]) -> list[TutorSpaceTier]:
    sorted_raw = sorted(raw_tiers, key=lambda t: float(t["hours_from"]))
    return [
        TutorSpaceTier(
            start_hour_inclusive=int(float(t["hours_from"])) + 1,
            rate_eur_per_hour=Decimal(str(t["rate"])),
        )
        for t in sorted_raw
    ]


def resolve_institute_billing_config(institute) -> InstituteBillingConfig | None:
    """
    Return the billing rules for this institute, or None for plain flat-rate billing
    (no tiers, tutor no-show billed normally).

    ``institute``: an ``Institute`` instance, or None (private lessons).
    """
    if institute is None:
        return None

    tiers = _tiers_from_json(institute.tiers) if institute.tiers else None
    if not tiers and not institute.unpaid_on_tutor_no_show:
        return None

    return InstituteBillingConfig(
        tiers=tiers,
        unpaid_on_tutor_no_show=institute.unpaid_on_tutor_no_show,
        tier_count_from=institute.tier_count_from if tiers else None,
        tutor_no_show_pay_percent=institute.tutor_no_show_pay_percent if tiers else 0,
    )


def calculate_tiered_amount(
    session, tutor: User, institute, config: InstituteBillingConfig
) -> Decimal:
    """Compute cumulative-tier-based pay for one session, given a resolved config with tiers."""
    if not config.tiers:
        raise ValueError("config has no tiers")

    duration = int(getattr(session, "duration_minutes", 0) or 0)
    if duration <= 0:
        return Decimal("0.00")

    minutes_before = minutes_before_session_for_institute(
        session, tutor, institute, config.tier_count_from
    )
    boundaries = tier_boundaries_minutes(config.tiers)
    amount = Decimal("0.00")
    remaining = duration
    cursor = minutes_before

    def next_boundary_after(minute_index: int) -> int | None:
        for b in boundaries:
            if b > minute_index:
                return b
        return None

    while remaining > 0:
        rate = rate_for_cumulative_minute(config.tiers, cursor)
        nb = next_boundary_after(cursor)
        chunk = remaining if nb is None else min(remaining, nb - cursor)
        amount += (Decimal(chunk) / Decimal("60")) * rate
        cursor += chunk
        remaining -= chunk

    if getattr(session, "tutor_no_show", False):
        pct = max(0, min(100, config.tutor_no_show_pay_percent))
        base = amount
        if pct < 100:
            amount = base * (Decimal(pct) / Decimal("100")) - base

    return amount.quantize(Decimal("0.01"))


def calculate_lesson_amount(
    lesson, tutor: User, config: InstituteBillingConfig | None = None
) -> Decimal:
    """
    Single source of truth for lesson compensation amount, shared by invoice creation,
    income selectors and finance metrics.

    ``config`` can be passed in by callers that already resolved it (e.g. to avoid
    re-resolving per lesson within a loop over the same institute).
    """
    contract = lesson.contract
    institute = contract.institute_fk
    if config is None:
        config = resolve_institute_billing_config(institute)

    if config and config.tiers:
        return calculate_tiered_amount(lesson, tutor, institute, config)

    unit_duration = Decimal(str(contract.unit_duration_minutes))
    if unit_duration == 0:
        raise ValueError("unit_duration_minutes darf nicht 0 sein")
    lesson_duration = Decimal(str(lesson.duration_minutes))
    units = lesson_duration / unit_duration
    amount = units * contract.hourly_rate

    if getattr(lesson, "tutor_no_show", False) and config and config.unpaid_on_tutor_no_show:
        return Decimal("0.00")

    return amount

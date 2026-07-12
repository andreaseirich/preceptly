"""
Generic per-institute billing rules: tiered compensation and tutor-no-show handling.

Any institute name a tutor uses on a Contract can get tiered compensation and/or a
"no billing on tutor no-show" rule by creating an ``InstituteTierConfig`` in Settings.
"TutorSpace" and "Abacus" are no longer special-cased in the calculation itself — they
are only used as built-in *default presets* so existing tutors who never opened the
tier-config settings keep getting the same behaviour they always had.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth.models import User

from apps.contracts.institute_utils import ABACUS_INSTITUTE_NAME, TUTORSPACE_INSTITUTE_NAME
from apps.contracts.tutorspace_compensation import (
    TIERS,
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


def _tiers_from_config(raw_tiers: list[dict]) -> list[TutorSpaceTier]:
    sorted_raw = sorted(raw_tiers, key=lambda t: float(t["hours_from"]))
    return [
        TutorSpaceTier(
            start_hour_inclusive=int(float(t["hours_from"])) + 1,
            rate_eur_per_hour=Decimal(str(t["rate"])),
        )
        for t in sorted_raw
    ]


def resolve_institute_billing_config(
    user: User, institute_name: str | None
) -> InstituteBillingConfig | None:
    """
    Return the billing rules for this institute, or None for plain flat-rate billing
    (no tiers, tutor no-show billed normally).
    """
    from apps.contracts.models import InstituteTierConfig
    from apps.core.models import UserProfile

    name = (institute_name or "").strip()
    if not name:
        return None

    config = InstituteTierConfig.objects.filter(user=user, institute_name__iexact=name).first()
    is_builtin_tutorspace = name.lower() == TUTORSPACE_INSTITUTE_NAME.lower()
    is_builtin_abacus = name.lower() == ABACUS_INSTITUTE_NAME.lower()

    if config is not None:
        tiers = _tiers_from_config(config.tiers) if config.tiers else None
        unpaid_on_no_show = config.unpaid_on_tutor_no_show
    elif is_builtin_tutorspace:
        tiers = list(TIERS)
        unpaid_on_no_show = False
    elif is_builtin_abacus:
        tiers = None
        unpaid_on_no_show = True
    else:
        return None

    tier_count_from = None
    if is_builtin_tutorspace:
        profile = UserProfile.objects.filter(user=user).first()
        tier_count_from = getattr(profile, "tutorspace_tier_count_from", None) if profile else None

    if not tiers and not unpaid_on_no_show:
        return None

    return InstituteBillingConfig(
        tiers=tiers, unpaid_on_tutor_no_show=unpaid_on_no_show, tier_count_from=tier_count_from
    )


def calculate_tiered_amount(
    session, tutor: User, institute_name: str, config: InstituteBillingConfig
) -> Decimal:
    """Compute cumulative-tier-based pay for one session, given a resolved config with tiers."""
    if not config.tiers:
        raise ValueError("config has no tiers")

    duration = int(getattr(session, "duration_minutes", 0) or 0)
    if duration <= 0:
        return Decimal("0.00")

    minutes_before = minutes_before_session_for_institute(
        session, tutor, institute_name, config.tier_count_from
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
        from apps.core.models import UserProfile

        profile = UserProfile.objects.filter(user=tutor).first()
        pct = int(getattr(profile, "tutor_no_show_pay_percent", 0) or 0) if profile else 0
        pct = max(0, min(100, pct))
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
    re-querying InstituteTierConfig per lesson within a loop over the same institute).
    """
    contract = lesson.contract
    institute_name = getattr(contract, "institute", None)
    if config is None:
        config = resolve_institute_billing_config(tutor, institute_name)

    if config and config.tiers:
        return calculate_tiered_amount(lesson, tutor, institute_name, config)

    unit_duration = Decimal(str(contract.unit_duration_minutes))
    if unit_duration == 0:
        raise ValueError("unit_duration_minutes darf nicht 0 sein")
    lesson_duration = Decimal(str(lesson.duration_minutes))
    units = lesson_duration / unit_duration
    amount = units * contract.hourly_rate

    if getattr(lesson, "tutor_no_show", False) and config and config.unpaid_on_tutor_no_show:
        return Decimal("0.00")

    return amount

"""
Services for contract-related calculations (e.g. monthly planning summary).
"""

from datetime import date, timedelta
from math import ceil

from django.utils.translation import gettext

from apps.contracts.formsets import iter_contract_months
from apps.contracts.models import Contract, ContractMonthlyPlan, Institute
from apps.contracts.tier_counting import COUNT_BY_STARTED_HOUR, counted_total, tier_pool
from apps.lessons.models import Lesson


def _month_planning_for_contract(
    contract: Contract, year: int, month: int, carried_over: int = 0
) -> dict:
    """Single month: planned, carried_over, taught, scheduled (in calendar), remaining."""
    start_d = date(year, month, 1)
    if month == 12:
        end_d = date(year + 1, 1, 1)
    else:
        end_d = date(year, month + 1, 1)

    plan = ContractMonthlyPlan.objects.filter(contract=contract, year=year, month=month).first()
    planned = plan.planned_units if plan else 0

    taught = Lesson.objects.filter(
        contract=contract,
        date__gte=start_d,
        date__lt=end_d,
        status__in=["taught", "paid"],
    ).count()

    scheduled = Lesson.objects.filter(
        contract=contract,
        date__gte=start_d,
        date__lt=end_d,
        status="planned",
    ).count()

    total_to_teach = planned + carried_over
    remaining = max(0, total_to_teach - taught - scheduled)
    return {
        "year": year,
        "month": month,
        "planned_units": planned,
        "carried_over_units": carried_over,
        "taught_units": taught,
        "scheduled_units": scheduled,
        "remaining_units": remaining,
    }


def get_contract_monthly_planning_summary(contract: Contract, year: int = None):
    """
    For a contract with monthly planning: per month, planned units, carried-over units
    (from previous month's remaining), taught units, and remaining units.
    Remaining hours from a month are added to the next month's target.

    Args:
        contract: Contract (should have has_monthly_planning_limit=True).
        year: If set, only return months for this year; else current year.

    Returns:
        List of dicts: {year, month, planned_units, carried_over_units, taught_units, remaining_units}.
    """
    if not contract.has_monthly_planning_limit:
        return []

    if year is None:
        year = date.today().year

    result = []
    carried_over = 0
    for y, m in iter_contract_months(contract.start_date, contract.end_date):
        row = _month_planning_for_contract(contract, y, m, carried_over)
        carried_over = row["remaining_units"]
        if y == year:
            result.append(row)
    return result


def get_contract_current_month_summary(contract: Contract):
    """
    For contract list: current month only: planned, carried_over, taught, remaining.
    Returns None if contract has no monthly planning.
    """
    if not contract.has_monthly_planning_limit:
        return None
    today = date.today()
    carried_over = _compute_carried_over_before(contract, today.year, today.month)
    return _month_planning_for_contract(contract, today.year, today.month, carried_over)


def _compute_carried_over_before(contract: Contract, before_year: int, before_month: int) -> int:
    """Remaining units from the last month before (before_year, before_month)."""
    carried = 0
    for y, m in iter_contract_months(contract.start_date, contract.end_date):
        if (y, m) >= (before_year, before_month):
            break
        row = _month_planning_for_contract(contract, y, m, carried)
        carried = row["remaining_units"]
    return carried


def get_institute_tier_progress(institute: Institute) -> dict | None:
    """Cumulative-hours tier progress for one Institute, or None if it has no tiers
    or its tier data is malformed."""
    tiers = institute.tiers

    # Defensive type-check vor dem Sortieren (verhindert TypeError bei unvalidiertem JSONField)
    # Zusätzlich: Label-Inhalte werden nie als |safe gerendert (Template-Verantwortung),
    # aber wir filtern hier defensiv XSS-verdächtige Labels heraus
    try:
        for t in tiers:
            if not isinstance(t, dict):
                return None
            hours_from = t.get("hours_from")
            if not isinstance(hours_from, (int, float)) or hours_from < 0:
                return None
            label = t.get("label", "")
            if not isinstance(label, str) or any(c in label for c in ("<", ">")):
                return None
        sorted_tiers = sorted(tiers, key=lambda t: float(t["hours_from"]))
    except (TypeError, KeyError, ValueError):
        return None

    # Leere Tier-Liste nach Sortierung → sicher abbrechen (verhindert IndexError)
    if not sorted_tiers:
        return None

    # Derselbe Pool und dieselbe Zählweise wie in der Abrechnung (tier_counting.py).
    mode = institute.tier_count_mode
    pool = tier_pool(institute)
    total_hours = round(
        float(
            counted_total(
                pool.values_list("duration_minutes", flat=True), mode, institute.tier_count_offset
            )
        ),
        2,
    )

    current_tier = sorted_tiers[0]
    for tier in sorted_tiers:
        if tier["hours_from"] <= total_hours:
            current_tier = tier

    next_tier = None
    for tier in sorted_tiers:
        if tier["hours_from"] > total_hours:
            next_tier = tier
            break

    hours_in_current_tier = round(total_hours - current_tier["hours_from"], 2)
    hours_until_next_tier = round(next_tier["hours_from"] - total_hours, 2) if next_tier else None

    today = date.today()
    recent = pool.filter(date__gte=today - timedelta(days=90))
    daily_rate = (
        float(counted_total(recent.values_list("duration_minutes", flat=True), mode)) / 90.0
    )

    estimated_date = None
    if daily_rate > 0 and hours_until_next_tier is not None:
        estimated_date = today + timedelta(days=ceil(hours_until_next_tier / daily_rate))

    return {
        "total_hours": total_hours,
        "current_tier_label": current_tier["label"],
        "hours_in_current_tier": hours_in_current_tier,
        "next_tier_label": next_tier["label"] if next_tier else None,
        "hours_until_next_tier": hours_until_next_tier,
        "estimated_date": estimated_date,
        "institute_name": institute.institute_name,
        "unit_label": gettext("units") if mode == COUNT_BY_STARTED_HOUR else "h",
        "start_value": institute.tier_count_offset,
    }

"""
Services for contract-related calculations (e.g. monthly planning summary).
"""

from datetime import date, timedelta
from decimal import Decimal
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


def _sorted_valid_tiers(institute: Institute) -> list[dict] | None:
    """Stufen des Instituts nach "ab Stunden" sortiert, oder None bei keinen oder kaputten Stufen."""
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
    return sorted_tiers or None


def _tier_total_hours(institute: Institute, pool) -> float:
    """Zählerstand des Instituts in Stunden bzw. Einheiten, einschließlich Startwert."""
    return round(
        float(
            counted_total(
                pool.values_list("duration_minutes", flat=True),
                institute.tier_count_mode,
                institute.tier_count_offset,
            )
        ),
        2,
    )


def _tier_at(sorted_tiers: list[dict], total_hours: float) -> dict:
    """Die Stufe, die beim Zählerstand total_hours gilt (bei null Stunden die erste)."""
    current_tier = sorted_tiers[0]
    for tier in sorted_tiers:
        if tier["hours_from"] <= total_hours:
            current_tier = tier
    return current_tier


def _money(value) -> Decimal | None:
    """Ein Betrag als Decimal, oder None, wenn er fehlt, kaputt oder kleiner als 0,01 ist."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < Decimal("0.01"):
            return None
    except (TypeError, ValueError, ArithmeticError):
        return None
    return amount


def new_student_defaults(institute: Institute) -> dict:
    """Was beim Anlegen eines Schülers dieses Instituts vorbelegt wird: {"rate", "duration"}.

    rate ist der Standard-Stundensatz des Instituts. Fehlt er, gilt der Satz der Stufe, in der der Tutor bei
    diesem Institut gerade steht (gleiche Zählweise wie die Abrechnung, bei null Stunden die erste Stufe).
    Er kommt als Text mit zwei Nachkommastellen; ohne Stufen, bei kaputten Stufen oder bei einem Satz unter
    0,01 ist er None. duration sind die Minuten oder None. None heißt: nichts vorbelegen."""
    rate = _money(institute.default_hourly_rate)
    if rate is None and institute.default_hourly_rate is None:
        sorted_tiers = _sorted_valid_tiers(institute)
        if sorted_tiers:
            total_hours = _tier_total_hours(institute, tier_pool(institute))
            rate = _money(_tier_at(sorted_tiers, total_hours).get("rate"))
    return {
        "rate": f"{rate:.2f}" if rate is not None else None,
        "duration": institute.default_unit_duration_minutes or None,
    }


def get_institute_tier_progress(institute: Institute) -> dict | None:
    """Cumulative-hours tier progress for one Institute, or None if it has no tiers
    or its tier data is malformed."""
    sorted_tiers = _sorted_valid_tiers(institute)
    if not sorted_tiers:
        return None

    # Derselbe Pool und dieselbe Zählweise wie in der Abrechnung (tier_counting.py).
    mode = institute.tier_count_mode
    pool = tier_pool(institute)
    total_hours = _tier_total_hours(institute, pool)
    current_tier = _tier_at(sorted_tiers, total_hours)

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

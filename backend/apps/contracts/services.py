"""
Services for contract-related calculations (e.g. monthly planning summary).
"""

from datetime import date, timedelta
from math import ceil

from django.db.models import Sum

from apps.contracts.formsets import iter_contract_months
from apps.contracts.models import Contract, ContractMonthlyPlan, InstituteTierConfig
from apps.lessons.models import Lesson, Session


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


# --- SERVICE ---


def get_institute_tier_progress(user, institute_name: str) -> dict | None:
    from apps.contracts.tutorspace_compensation import TIERS
    from apps.core.models import UserProfile

    config = InstituteTierConfig.objects.filter(
        user=user, institute_name__iexact=institute_name
    ).first()

    if config:
        tiers = config.tiers
    elif institute_name.lower() == "tutorspace":
        tiers = [
            {
                "hours_from": tier.start_hour_inclusive - 1,
                "label": f"{tier.rate_eur_per_hour} €/h",
            }
            for tier in TIERS
        ]
    else:
        return None

    qs = Session.objects.filter(
        contract__student__user=user,
        contract__institute__iexact=institute_name,
        status__in=["taught", "paid"],
    )

    if institute_name.lower() == "tutorspace":
        profile = UserProfile.objects.filter(user=user).first()
        tier_from = getattr(profile, "tutorspace_tier_count_from", None) if profile else None
        if tier_from is not None:
            qs = qs.filter(date__gte=tier_from)

    total_minutes = qs.aggregate(total=Sum("duration_minutes"))["total"] or 0
    total_hours = round(total_minutes / 60.0, 2)

    sorted_tiers = sorted(tiers, key=lambda t: t["hours_from"])
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
    recent_qs = Session.objects.filter(
        contract__student__user=user,
        contract__institute__iexact=institute_name,
        status__in=["taught", "paid"],
        date__gte=today - timedelta(days=90),
    )
    recent_minutes = recent_qs.aggregate(total=Sum("duration_minutes"))["total"] or 0
    daily_rate = recent_minutes / 60.0 / 90.0

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
        "institute_name": institute_name,
    }


def get_institute_tier_progress(user, institute_name: str) -> dict | None:
    from math import ceil
    from datetime import date, timedelta

    from django.db.models import Sum

    from apps.contracts.models import InstituteTierConfig
    from apps.contracts.tutorspace_compensation import TIERS as TUTORSPACE_TIERS
    from apps.core.models import UserProfile
    from apps.lessons.models import Session

    config = InstituteTierConfig.objects.filter(
        user=user, institute_name__iexact=institute_name
    ).first()

    if config:
        tiers_data = config.tiers
    elif institute_name.lower() == "tutorspace":
        tiers_data = [
            {"hours_from": t.start_hour_inclusive - 1, "label": str(t.rate_eur_per_hour) + " €/h"}
            for t in TUTORSPACE_TIERS
        ]
    else:
        return None

    qs = Session.objects.filter(
        contract__student__user=user,
        contract__institute__iexact=institute_name,
        status__in=["taught", "paid"],
    )

    if institute_name.lower() == "tutorspace":
        profile = UserProfile.objects.filter(user=user).first()
        tier_from = getattr(profile, "tutorspace_tier_count_from", None)
        if tier_from:
            qs = qs.filter(date__gte=tier_from)

    total_minutes = qs.aggregate(total=Sum("duration_minutes"))["total"] or 0
    total_hours = round(total_minutes / 60.0, 2)

    sorted_tiers = sorted(tiers_data, key=lambda t: t["hours_from"])

    current_tier = sorted_tiers[0]
    for tier in sorted_tiers:
        if tier["hours_from"] <= total_hours:
            current_tier = tier

    idx = sorted_tiers.index(current_tier)
    next_tier = sorted_tiers[idx + 1] if idx + 1 < len(sorted_tiers) else None

    hours_in_current_tier = round(total_hours - current_tier["hours_from"], 2)
    hours_until_next_tier = round(next_tier["hours_from"] - total_hours, 2) if next_tier else None

    ninety_days_ago = date.today() - timedelta(days=90)
    recent_qs = Session.objects.filter(
        contract__student__user=user,
        contract__institute__iexact=institute_name,
        status__in=["taught", "paid"],
        date__gte=ninety_days_ago,
    )
    recent_minutes = recent_qs.aggregate(total=Sum("duration_minutes"))["total"] or 0
    daily_rate = recent_minutes / 60.0 / 90
    estimated_date = (
        date.today() + timedelta(days=ceil(hours_until_next_tier / daily_rate))
        if daily_rate > 0 and hours_until_next_tier
        else None
    )

    return {
        "total_hours": total_hours,
        "current_tier_label": current_tier["label"],
        "hours_in_current_tier": hours_in_current_tier,
        "next_tier_label": next_tier["label"] if next_tier else None,
        "hours_until_next_tier": hours_until_next_tier,
        "estimated_date": estimated_date,
        "institute_name": institute_name,
    }

"""
Services for contract-related calculations (e.g. monthly planning summary).
"""

from datetime import date

from apps.contracts.formsets import iter_contract_months
from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.lessons.models import Lesson


def _month_planning_for_contract(contract: Contract, year: int, month: int) -> dict:
    """Single month: planned, taught, remaining."""
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

    remaining = max(0, planned - taught)
    return {
        "year": year,
        "month": month,
        "planned_units": planned,
        "taught_units": taught,
        "remaining_units": remaining,
    }


def get_contract_monthly_planning_summary(contract: Contract, year: int = None):
    """
    For a contract with monthly planning: per month, planned units, taught units,
    and remaining units (planned - taught). "Taught" = lessons with status taught or paid.

    Args:
        contract: Contract (should have has_monthly_planning_limit=True).
        year: If set, only return months for this year; else current year.

    Returns:
        List of dicts: {year, month, planned_units, taught_units, remaining_units}.
    """
    if not contract.has_monthly_planning_limit:
        return []

    if year is None:
        year = date.today().year

    result = []
    for y, m in iter_contract_months(contract.start_date, contract.end_date):
        if y != year:
            continue
        result.append(_month_planning_for_contract(contract, y, m))
    return result


def get_contract_current_month_summary(contract: Contract):
    """
    For contract list: current month only: planned, taught, remaining.
    Returns None if contract has no monthly planning.
    """
    if not contract.has_monthly_planning_limit:
        return None
    today = date.today()
    return _month_planning_for_contract(contract, today.year, today.month)

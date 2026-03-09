"""
Services for contract-related calculations (e.g. monthly planning summary).
"""

from datetime import date

from apps.contracts.formsets import iter_contract_months
from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.lessons.models import Lesson


def _month_planning_for_contract(
    contract: Contract, year: int, month: int, carried_over: int = 0
) -> dict:
    """Single month: planned, carried_over, taught, remaining."""
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

    total_to_teach = planned + carried_over
    remaining = max(0, total_to_teach - taught)
    return {
        "year": year,
        "month": month,
        "planned_units": planned,
        "carried_over_units": carried_over,
        "taught_units": taught,
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

"""
Canonical definitions for revenue and statistics.

All metrics are owner-scoped (Invoice.owner / Lesson via contract->student->user).
Revenue is always based on Invoice.total_amount; never on Lesson.status directly.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from apps.billing.models import Invoice, InvoiceItem
from apps.lessons.models import Lesson
from django.contrib.auth.models import User
from django.db.models import Sum


class InvoiceStatus(StrEnum):
    """Invoice status constants."""

    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"


def _month_range(year: int, month: int) -> tuple[date, date]:
    """Return (start_date, end_date) for a month."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _invoices_for_month(user: User, year: int, month: int, status_filter: list[str] | None = None):
    """Owner-scoped invoices for period by period_start."""
    qs = Invoice.objects.filter(
        owner=user,
        period_start__year=year,
        period_start__month=month,
    )
    if status_filter is not None:
        qs = qs.filter(status__in=status_filter)
    return qs


# ---------------------------------------------------------------------------
# Revenue (Invoice-based only)
# ---------------------------------------------------------------------------


def recognized_revenue(user: User, year: int, month: int) -> Decimal:
    """Sum of Invoice.total_amount where status == PAID. Owner-scoped."""
    total = _invoices_for_month(user, year, month, [InvoiceStatus.PAID]).aggregate(
        s=Sum("total_amount")
    )["s"] or Decimal("0")
    return total


def pending_revenue(user: User, year: int, month: int) -> Decimal:
    """Sum of Invoice.total_amount where status == SENT. Owner-scoped."""
    total = _invoices_for_month(user, year, month, [InvoiceStatus.SENT]).aggregate(
        s=Sum("total_amount")
    )["s"] or Decimal("0")
    return total


def total_billed_revenue(user: User, year: int, month: int) -> Decimal:
    """Sum of Invoice.total_amount where status in (PAID, SENT). Owner-scoped."""
    total = _invoices_for_month(
        user, year, month, [InvoiceStatus.PAID, InvoiceStatus.SENT]
    ).aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
    return total


# ---------------------------------------------------------------------------
# Hours (Lesson-based; status reflects invoice workflow via PaymentService)
# ---------------------------------------------------------------------------


def taught_hours(user: User, year: int, month: int) -> float:
    """Minutes of lessons with status in (taught, paid), aggregated. Owner-scoped."""
    start_d, end_d = _month_range(year, month)
    mins = (
        Lesson.objects.filter(
            contract__student__user=user,
            date__gte=start_d,
            date__lt=end_d,
            status__in=("taught", "paid"),
        ).aggregate(s=Sum("duration_minutes"))["s"]
        or 0
    )
    return round(mins / 60, 1)


def paid_hours(user: User, year: int, month: int) -> float:
    """Minutes of lessons with status == paid, aggregated. Owner-scoped."""
    start_d, end_d = _month_range(year, month)
    mins = (
        Lesson.objects.filter(
            contract__student__user=user,
            date__gte=start_d,
            date__lt=end_d,
            status=InvoiceStatus.PAID,
        ).aggregate(s=Sum("duration_minutes"))["s"]
        or 0
    )
    return round(mins / 60, 1)


def lesson_count_taught_or_paid(user: User, year: int, month: int) -> int:
    """Count of lessons with status in (taught, paid). Owner-scoped."""
    start_d, end_d = _month_range(year, month)
    return Lesson.objects.filter(
        contract__student__user=user,
        date__gte=start_d,
        date__lt=end_d,
        status__in=("taught", "paid"),
    ).count()


# ---------------------------------------------------------------------------
# Reports helpers
# ---------------------------------------------------------------------------


def revenue_per_month_last_n(user: User, now, n: int = 6) -> list[dict]:
    """Revenue (recognized = PAID only) per month for last n months."""
    result = []
    for i in range(n):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        rev = recognized_revenue(user, y, m)
        result.append({"year": y, "month": m, "revenue": rev})
    return list(reversed(result))


def hours_per_month_last_n(user: User, now, n: int = 6) -> list[dict]:
    """Taught hours per month for last n months."""
    result = []
    for i in range(n):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        h = taught_hours(user, y, m)
        result.append({"year": y, "month": m, "hours": h})
    return list(reversed(result))


def breakdown_by_institute_recognized(user: User, year: int, month: int) -> list[dict]:
    """Revenue by institute, PAID invoices only. Owner-scoped."""
    invs = _invoices_for_month(user, year, month, [InvoiceStatus.PAID]).select_related("contract")
    by_inst = {}
    for inv in invs:
        inst = (inv.contract.institute or "").strip() if inv.contract else ""
        if not inst:
            inst = "-"
        by_inst[inst] = by_inst.get(inst, Decimal("0")) + inv.total_amount
    return [{"institute": k, "revenue": v} for k, v in sorted(by_inst.items(), key=lambda x: -x[1])]


def breakdown_by_institute_billed(user: User, year: int, month: int) -> list[dict]:
    """Revenue by institute, PAID + SENT invoices. Owner-scoped."""
    invs = _invoices_for_month(
        user, year, month, [InvoiceStatus.PAID, InvoiceStatus.SENT]
    ).select_related("contract")
    by_inst = {}
    for inv in invs:
        inst = (inv.contract.institute or "").strip() if inv.contract else ""
        if not inst:
            inst = "-"
        by_inst[inst] = by_inst.get(inst, Decimal("0")) + inv.total_amount
    return [{"institute": k, "revenue": v} for k, v in sorted(by_inst.items(), key=lambda x: -x[1])]


def unpaid_invoices(user: User) -> dict:
    """Count and total amount of invoices with status draft or sent."""
    invs = Invoice.objects.filter(owner=user, status__in=[InvoiceStatus.DRAFT, InvoiceStatus.SENT])
    count = invs.count()
    total = invs.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
    return {"count": count, "amount": total}


def taught_not_invoiced(user: User, year: int, month: int) -> dict:
    """Taught lessons not in any invoice; value = computed from duration * rate."""
    from apps.core.selectors import IncomeSelector

    start_d, end_d = _month_range(year, month)
    taught = Lesson.objects.filter(
        contract__student__user=user,
        date__gte=start_d,
        date__lt=end_d,
        status__in=("taught", "paid"),
    ).select_related("contract")
    count = 0
    value = Decimal("0")
    for les in taught:
        if not InvoiceItem.objects.filter(lesson=les).exists():
            count += 1
            value += IncomeSelector._calculate_lesson_amount(les)
    return {"count": count, "value": value}


def top_students_by_recognized_revenue(
    user: User, year: int, month: int, limit: int = 5
) -> list[dict]:
    """
    Top students by recognized revenue (PAID invoices) for the month.
    Returns list of {contract, lessons, income} where income is from PAID invoices
    for that contract.
    """
    invs = (
        _invoices_for_month(user, year, month, [InvoiceStatus.PAID])
        .filter(contract__isnull=False)
        .select_related("contract", "contract__student")
    )
    by_contract = {}
    for inv in invs:
        c = inv.contract
        if c.id not in by_contract:
            by_contract[c.id] = {
                "contract": c,
                "lessons": 0,
                "income": Decimal("0"),
            }
        by_contract[c.id]["income"] += inv.total_amount
    start_d, end_d = _month_range(year, month)
    for cid, data in by_contract.items():
        lessons = Lesson.objects.filter(
            contract_id=cid,
            date__gte=start_d,
            date__lt=end_d,
            status__in=("taught", "paid"),
        ).count()
        data["lessons"] = lessons
    sorted_list = sorted(by_contract.values(), key=lambda x: x["income"], reverse=True)
    return sorted_list[:limit]


def invoice_count_for_month(user: User, year: int, month: int) -> int:
    """Count of all invoices for the month. Owner-scoped."""
    return _invoices_for_month(user, year, month).count()

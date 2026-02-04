"""
Reports/Stats view for tutors. Premium: full analytics. Basic: teaser.
"""

from datetime import date
from decimal import Decimal

from apps.billing.models import Invoice, InvoiceItem
from apps.core.feature_flags import Feature, user_has_feature
from apps.core.selectors import IncomeSelector
from apps.lessons.models import Lesson
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.utils import timezone
from django.views.generic import TemplateView


def _revenue_per_month_last_6(user, now):
    """Revenue per month (last 6 months) from paid invoices."""
    result = []
    for i in range(6):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        invs = Invoice.objects.filter(
            owner=user,
            status="paid",
            period_start__year=y,
            period_start__month=m,
        )
        total = invs.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
        result.append({"year": y, "month": m, "revenue": total})
    return list(reversed(result))


def _hours_per_month_last_6(user, now):
    """Hours taught per month (last 6 months)."""
    result = []
    for i in range(6):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        start_d = date(y, m, 1)
        end_d = date(y, m + 1, 1) if m < 12 else date(y + 1, 1, 1)
        mins = (
            Lesson.objects.filter(
                contract__student__user=user,
                date__gte=start_d,
                date__lt=end_d,
                status__in=("taught", "paid"),
            ).aggregate(s=Sum("duration_minutes"))["s"]
            or 0
        )
        result.append({"year": y, "month": m, "hours": round(mins / 60, 1)})
    return list(reversed(result))


def _breakdown_by_institute(user, year, month):
    """Revenue by institute for selected month (invoices paid/sent)."""
    invs = Invoice.objects.filter(
        owner=user,
        status__in=("paid", "sent"),
        period_start__year=year,
        period_start__month=month,
    ).select_related("contract")
    by_inst = {}
    for inv in invs:
        inst = (inv.contract.institute or "").strip() if inv.contract else ""
        if not inst:
            inst = "-"
        by_inst[inst] = by_inst.get(inst, Decimal("0")) + inv.total_amount
    return [{"institute": k, "revenue": v} for k, v in sorted(by_inst.items(), key=lambda x: -x[1])]


def _unpaid_invoices(user):
    """Unpaid invoices count and total amount."""
    invs = Invoice.objects.filter(owner=user, status__in=("draft", "sent"))
    count = invs.count()
    total = invs.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
    return {"count": count, "amount": total}


def _taught_not_invoiced(user, year, month):
    """Taught lessons not yet in any invoice; value = minutes * hourly_rate."""
    start_d = date(year, month, 1)
    end_d = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
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


class ReportsView(LoginRequiredMixin, TemplateView):
    """Reports page: Premium gets full analytics, Basic gets teaser."""

    template_name = "core/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_premium = user_has_feature(user, Feature.FEATURE_REPORTS)
        now = timezone.now()
        year = int(self.request.GET.get("year", now.year))
        month = int(self.request.GET.get("month", now.month))

        if not (1 <= month <= 12 and 2000 <= year <= 2100):
            year, month = now.year, now.month

        start_date = date(year, month, 1)
        end_date = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

        lessons = Lesson.objects.filter(
            date__gte=start_date,
            date__lt=end_date,
            status__in=("taught", "paid"),
            contract__student__user=user,
        )
        taught_minutes = lessons.aggregate(s=Sum("duration_minutes"))["s"] or 0
        lesson_count = lessons.count()

        invoices = Invoice.objects.filter(
            owner=user,
            period_start__year=year,
            period_start__month=month,
        )
        invoice_count = invoices.count()
        paid_from_invoices = sum(inv.total_amount for inv in invoices.filter(status="paid"))

        income_data = IncomeSelector.get_monthly_income(year, month, status="paid", user=user)
        details = income_data.get("contract_details", [])
        top_students = sorted(details, key=lambda x: x["income"], reverse=True)[:5]

        context["year"] = year
        context["month"] = month
        context["taught_minutes"] = taught_minutes
        context["taught_hours"] = round(taught_minutes / 60, 1)
        context["lesson_count"] = lesson_count
        context["paid_amount"] = paid_from_invoices
        context["invoice_count"] = invoice_count
        context["income_data"] = income_data
        context["contract_details"] = top_students
        context["is_premium"] = is_premium

        if is_premium:
            context["revenue_last_6"] = _revenue_per_month_last_6(user, now)
            context["hours_last_6"] = _hours_per_month_last_6(user, now)
            context["breakdown_by_institute"] = _breakdown_by_institute(user, year, month)
            context["unpaid_invoices"] = _unpaid_invoices(user)
            context["taught_not_invoiced"] = _taught_not_invoiced(user, year, month)

        return context

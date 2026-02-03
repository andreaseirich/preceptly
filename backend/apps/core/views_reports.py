"""
Reports/Stats view for tutors. Premium: full page. Basic: teaser.
"""

from apps.core.feature_flags import Feature, user_has_feature
from apps.core.selectors import IncomeSelector
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView


class ReportsView(LoginRequiredMixin, TemplateView):
    """Reports page: Premium gets full stats, Basic gets teaser."""

    template_name = "core/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_premium = user_has_feature(user, Feature.FEATURE_REPORTS)

        now = timezone.now()
        year = int(self.request.GET.get("year", now.year))
        month = int(self.request.GET.get("month", now.month))

        if 1 <= month <= 12 and 2000 <= year <= 2100:
            income_data = IncomeSelector.get_monthly_income(year, month, status="paid", user=user)
            taught_minutes = 0
            from datetime import date

            from apps.lessons.models import Lesson

            start_date = date(year, month, 1)
            end_date = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
            lessons = Lesson.objects.filter(
                date__gte=start_date,
                date__lt=end_date,
                status__in=("taught", "paid"),
            ).filter(contract__student__user=user)
            taught_minutes = sum(les.duration_minutes for les in lessons)

            from apps.billing.models import Invoice
            from django.db.models import Q

            invoices = Invoice.objects.filter(
                Q(contract__student__user=user) | Q(items__lesson__contract__student__user=user),
                period_start__year=year,
                period_start__month=month,
            ).distinct()
            invoice_count = invoices.count()
            paid_from_invoices = sum(inv.total_amount for inv in invoices.filter(status="paid"))

            context["year"] = year
            context["month"] = month
            context["taught_minutes"] = taught_minutes
            context["taught_hours"] = round(taught_minutes / 60, 1)
            context["paid_amount"] = paid_from_invoices
            context["invoice_count"] = invoice_count
            context["income_data"] = income_data
            details = income_data.get("contract_details", [])
            details_sorted = sorted(details, key=lambda x: x["income"], reverse=True)[:5]
            context["contract_details"] = details_sorted
        else:
            context["year"] = now.year
            context["month"] = now.month
            context["taught_minutes"] = 0
            context["taught_hours"] = 0.0
            context["paid_amount"] = 0
            context["invoice_count"] = 0
            context["income_data"] = {}
            context["contract_details"] = []

        context["is_premium"] = is_premium
        return context

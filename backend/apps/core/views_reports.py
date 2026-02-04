"""
Reports/Stats view for tutors. Premium: full analytics. Basic: teaser.

Uses canonical finance_metrics for all revenue and hour calculations.
"""

from apps.core.feature_flags import Feature, user_has_feature
from apps.core.finance_metrics import (
    breakdown_by_institute_billed,
    breakdown_by_institute_recognized,
    hours_per_month_last_n,
    invoice_count_for_month,
    lesson_count_taught_or_paid,
    recognized_revenue,
    revenue_per_month_last_n,
    taught_hours,
    taught_not_invoiced,
    top_students_by_recognized_revenue,
    unpaid_invoices,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView


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

        lesson_count = lesson_count_taught_or_paid(user, year, month)
        taught_hours_val = taught_hours(user, year, month)
        paid_amount = recognized_revenue(user, year, month)
        invoice_count = invoice_count_for_month(user, year, month)
        top_students = top_students_by_recognized_revenue(user, year, month, limit=5)

        context["year"] = year
        context["month"] = month
        context["taught_hours"] = taught_hours_val
        context["lesson_count"] = lesson_count
        context["paid_amount"] = paid_amount
        context["invoice_count"] = invoice_count
        context["contract_details"] = top_students
        context["is_premium"] = is_premium

        if is_premium:
            context["revenue_last_6"] = revenue_per_month_last_n(user, now, 6)
            context["hours_last_6"] = hours_per_month_last_n(user, now, 6)
            context["breakdown_recognized"] = breakdown_by_institute_recognized(user, year, month)
            context["breakdown_billed"] = breakdown_by_institute_billed(user, year, month)
            context["unpaid_invoices"] = unpaid_invoices(user)
            context["taught_not_invoiced"] = taught_not_invoiced(user, year, month)

        return context

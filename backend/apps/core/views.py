"""
Views for dashboard and income overview.
"""

import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.billing.models import Invoice
from apps.core.forms import (
    ExpenseForm,
    TravelPolicyForm,
    TutorNoShowPayForm,
    TutorSpaceTierCountFromForm,
    UserEmailForm,
    WorkingHoursForm,
)
from apps.core.models import Expense, UserProfile
from apps.core.selectors import IncomeSelector
from apps.core.utils_booking import ensure_public_booking_token
from apps.lessons.services import LessonConflictService, SessionQueryService
from apps.lessons.status_service import SessionStatusUpdater

LEGAL_LAST_UPDATED = "08.04.2026"


class LandingPageView(TemplateView):
    """Landing page with demo mode and public booking options."""

    template_name = "core/landing.html"


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard with overview of today's lessons, conflicts, and income."""

    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Automatic status update for past sessions
        SessionStatusUpdater.update_past_sessions_to_taught()

        now = timezone.now()
        user = self.request.user

        # Today's sessions
        today_sessions = SessionQueryService.get_today_sessions(user=user)
        for session in today_sessions:
            session.conflicts = LessonConflictService.check_conflicts(session)

        # Upcoming sessions
        upcoming_sessions = SessionQueryService.get_upcoming_sessions(days=7, user=user)
        for session in upcoming_sessions:
            session.conflicts = LessonConflictService.check_conflicts(session)

        # Count conflicts (convert both QuerySets to lists for combination)
        all_sessions = list(today_sessions) + list(upcoming_sessions)
        conflict_count = sum(1 for session in all_sessions if session.conflicts)

        # Income for current month
        current_month_income = IncomeSelector.get_monthly_income(
            now.year, now.month, status="paid", user=user
        )

        # Income by status for current month
        income_by_status = IncomeSelector.get_income_by_status(
            year=now.year, month=now.month, user=user
        )

        # Premium status
        from apps.core.utils import is_premium_user

        context["is_premium"] = (
            is_premium_user(self.request.user) if self.request.user.is_authenticated else False
        )

        context.update(
            {
                "today_lessons": today_sessions,  # Keep 'today_lessons' for template compatibility
                "upcoming_lessons": upcoming_sessions,  # Keep 'upcoming_lessons' for template compatibility
                "conflict_count": conflict_count,
                "current_month_income": current_month_income,
                "income_by_status": income_by_status,
                "current_year": now.year,
                "current_month": now.month,
            }
        )

        return context


class IncomeOverviewView(LoginRequiredMixin, TemplateView):
    """Income overview with monthly and yearly views."""

    template_name = "core/income_overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Automatic status update for past sessions
        SessionStatusUpdater.update_past_sessions_to_taught()

        now = timezone.now()

        # Year and month from URL parameters or current date
        # Default to current month view if no month specified
        year = int(self.request.GET.get("year", now.year))
        if "month" in self.request.GET:
            month = int(self.request.GET.get("month"))
        elif "year" in self.request.GET:
            # If only year is specified, show year view
            month = None
        else:
            # Default to current month
            month = now.month

        # Calculate previous and next month/year for navigation
        if month:
            # Previous month
            if month == 1:
                prev_year = year - 1
                prev_month = 12
            else:
                prev_year = year
                prev_month = month - 1

            # Next month
            if month == 12:
                next_year = year + 1
                next_month = 1
            else:
                next_year = year
                next_month = month + 1
        else:
            prev_year = year - 1
            prev_month = 12
            next_year = year + 1
            next_month = 1

        user = self.request.user
        if month:
            # Monthly view
            monthly_income = IncomeSelector.get_monthly_income(
                year, month, status="paid", user=user
            )
            income_by_status = IncomeSelector.get_income_by_status(
                year=year, month=month, user=user
            )
            context.update(
                {
                    "view_type": "month",
                    "year": year,
                    "month": month,
                    "monthly_income": monthly_income,
                    "income_by_status": income_by_status,
                    "prev_year": prev_year,
                    "prev_month": prev_month,
                    "next_year": next_year,
                    "next_month": next_month,
                }
            )
        else:
            # Yearly view
            yearly_income = IncomeSelector.get_yearly_income(year, status="paid", user=user)
            income_by_status = IncomeSelector.get_income_by_status(year=year, user=user)
            context.update(
                {
                    "view_type": "year",
                    "year": year,
                    "yearly_income": yearly_income,
                    "income_by_status": income_by_status,
                    "prev_year": prev_year,
                    "prev_month": prev_month,
                    "next_year": next_year,
                    "next_month": next_month,
                }
            )

        return context


class SettingsView(LoginRequiredMixin, FormView):
    """Settings view for managing default working hours."""

    form_class = WorkingHoursForm
    template_name = "core/settings.html"
    success_url = reverse_lazy("core:settings")

    def get_initial(self):
        """Load current working hours from user profile."""
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return {"initial_working_hours": profile.default_working_hours or {}}

    def get_form_kwargs(self):
        """Pass initial working hours to form."""
        kwargs = super().get_form_kwargs()
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        kwargs["initial_working_hours"] = profile.default_working_hours or {}
        return kwargs

    def form_valid(self, form):
        """Save working hours to user profile."""
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        profile.default_working_hours = form.cleaned_data["working_hours"]
        profile.save()
        messages.success(self.request, _("Default working hours updated successfully."))
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        """Handle WorkingHoursForm, UserEmailForm, and TravelPolicyForm."""
        if "save_email" in request.POST:
            form = UserEmailForm(request.POST, instance=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, _("Email updated successfully."))
                return redirect(self.success_url)
            context = self.get_context_data()
            context["email_form"] = form
            return self.render_to_response(context)
        if "save_travel" in request.POST:
            travel_form = TravelPolicyForm(request.POST)
            if travel_form.is_valid():
                profile, _created = UserProfile.objects.get_or_create(user=request.user)
                policy = dict(profile.travel_policy or {})
                policy["transport_mode"] = travel_form.cleaned_data["transport_mode"]
                policy["fahrrad_buffer_minutes"] = (
                    travel_form.cleaned_data.get("fahrrad_buffer_minutes") or 25
                )
                policy["enabled"] = True
                profile.travel_policy = policy
                profile.save()
                messages.success(
                    request,
                    _("Travel mode for on-site appointments updated."),
                )
                return redirect(self.success_url)
            context = self.get_context_data()
            context["travel_form"] = travel_form
            return self.render_to_response(context)
        if "save_tutor_no_show" in request.POST:
            ns_form = TutorNoShowPayForm(request.POST)
            if ns_form.is_valid():
                profile, _created = UserProfile.objects.get_or_create(user=request.user)
                profile.tutor_no_show_pay_percent = ns_form.cleaned_data[
                    "tutor_no_show_pay_percent"
                ]
                profile.save()
                messages.success(
                    request,
                    _("TutorSpace: pay when you missed (student waited) saved."),
                )
                return redirect(self.success_url)
            context = self.get_context_data()
            context["tutor_no_show_form"] = ns_form
            return self.render_to_response(context)
        if "save_tutorspace_tier_from" in request.POST:
            tier_form = TutorSpaceTierCountFromForm(request.POST)
            if tier_form.is_valid():
                profile, _created = UserProfile.objects.get_or_create(user=request.user)
                profile.tutorspace_tier_count_from = tier_form.cleaned_data[
                    "tutorspace_tier_count_from"
                ]
                profile.save()
                messages.success(
                    request,
                    _("TutorSpace tier counting start date saved."),
                )
                return redirect(self.success_url)
            context = self.get_context_data()
            context["tutorspace_tier_form"] = tier_form
            return self.render_to_response(context)
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add profile, contracts, and booking links to context."""
        from django.conf import settings

        from apps.contracts.models import Contract
        from apps.core.feature_flags import is_premium_user
        from apps.core.stripe_utils import _is_valid_email_for_stripe

        context = super().get_context_data(**kwargs)
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        ensure_public_booking_token(profile)
        profile.refresh_from_db()

        context["is_premium"] = is_premium_user(self.request.user)
        context["is_demo_user"] = self.request.user.username in ("demo_premium", "demo_user")
        context["stripe_enabled"] = getattr(settings, "STRIPE_ENABLED", False)
        context["stripe_premium_checkout_enabled"] = getattr(
            settings, "STRIPE_PREMIUM_CHECKOUT_ENABLED", False
        )
        q = self.request.GET
        context["show_stripe_success_banner"] = (
            q.get("stripe_success") == "1" or q.get("checkout") == "success"
        )
        context["profile"] = profile
        context["show_email_recommendation"] = not _is_valid_email_for_stripe(
            self.request.user.email
        )
        context["email_form"] = UserEmailForm(instance=self.request.user)
        policy = getattr(profile, "travel_policy", None) or {}
        context["travel_form"] = TravelPolicyForm(
            initial={
                "transport_mode": policy.get("transport_mode", "oepnv"),
                "fahrrad_buffer_minutes": policy.get("fahrrad_buffer_minutes", 25),
            }
        )
        context["tutor_no_show_form"] = kwargs.get("tutor_no_show_form") or TutorNoShowPayForm(
            initial={
                "tutor_no_show_pay_percent": getattr(profile, "tutor_no_show_pay_percent", 0) or 0,
            }
        )
        context["tutorspace_tier_form"] = kwargs.get(
            "tutorspace_tier_form"
        ) or TutorSpaceTierCountFromForm(
            initial={
                "tutorspace_tier_count_from": getattr(profile, "tutorspace_tier_count_from", None),
            }
        )

        contracts = (
            Contract.objects.filter(is_active=True, student__user=self.request.user)
            .select_related("student")
            .order_by("student__last_name", "student__first_name")
        )
        context["profile"] = profile
        context["current_working_hours"] = profile.default_working_hours or {}
        context["contracts"] = contracts
        context["public_booking_url"] = self.request.build_absolute_uri(
            reverse(
                "lessons:public_booking_with_token",
                kwargs={"tutor_token": profile.public_booking_token},
            )
        )
        context["contract_booking_urls"] = [
            {
                "contract": c,
                "url": self.request.build_absolute_uri(
                    reverse("lessons:student_booking", kwargs={"token": c.booking_token})
                ),
            }
            for c in contracts
        ]
        return context


class LegalPageView(TemplateView):
    """Base view for legal pages."""

    last_updated = LEGAL_LAST_UPDATED

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["last_updated"] = self.last_updated
        return context


class LegalImprintView(LegalPageView):
    """Imprint page."""

    template_name = "legal/imprint.html"


class LegalPrivacyView(LegalPageView):
    """Privacy policy page."""

    template_name = "legal/privacy.html"


class LegalTermsView(LegalPageView):
    """Terms of service page."""

    template_name = "legal/terms.html"


class LegalAboutView(LegalPageView):
    """About page."""

    template_name = "legal/about.html"


class TaxYearView(LoginRequiredMixin, TemplateView):
    """Tax year overview based on cash-basis accounting (Zufluss-Prinzip / EÜR)."""

    template_name = "core/tax_year.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()

        from apps.core.feature_flags import is_premium_user

        is_premium = is_premium_user(user)

        try:
            year = int(self.request.GET.get("year", now.year))
        except (ValueError, TypeError):
            year = now.year

        available_year_dates = (
            Invoice.objects.filter(owner=user, paid_at__isnull=False)
            .dates("paid_at", "year")
            .order_by("-paid_at")
        )
        available_years = [d.year for d in available_year_dates]
        if year not in available_years:
            available_years = sorted(set(available_years + [year]), reverse=True)

        limit = Decimal("25000.00") if year >= 2025 else Decimal("22000.00")

        if is_premium:
            invoices = list(
                Invoice.objects.filter(
                    owner=user,
                    status="paid",
                    paid_at__isnull=False,
                    paid_at__year=year,
                )
                .order_by("paid_at")
                .only("invoice_number", "payer_name", "paid_at", "total_amount")
            )
            total_income = sum((inv.total_amount for inv in invoices), Decimal("0.00"))
            monthly_income = {m: Decimal("0.00") for m in range(1, 13)}
            for inv in invoices:
                monthly_income[inv.paid_at.month] += inv.total_amount
        else:
            invoices = []
            total_income = Decimal("0.00")
            monthly_income = {m: Decimal("0.00") for m in range(1, 13)}

        remaining = max(Decimal("0.00"), limit - total_income)

        expenses_qs = list(Expense.objects.filter(user=user, date__year=year))
        total_expenses = sum((e.effective_amount for e in expenses_qs), Decimal("0.00"))

        monthly_expense_totals = {m: Decimal("0.00") for m in range(1, 13)}
        for e in expenses_qs:
            monthly_expense_totals[e.date.month] += e.effective_amount

        monthly_breakdown = [
            {
                "month": m,
                "income": monthly_income[m],
                "expenses": monthly_expense_totals[m],
                "profit": monthly_income[m] - monthly_expense_totals[m],
            }
            for m in range(1, 13)
        ]

        total_profit = total_income - total_expenses

        category_labels = dict(Expense.CATEGORY_CHOICES)
        category_sums: dict = {}
        for e in expenses_qs:
            label = category_labels.get(e.category, e.category)
            category_sums[label] = category_sums.get(label, Decimal("0.00")) + e.effective_amount
        expenses_by_category = {k: v for k, v in category_sums.items() if v > 0}

        context.update(
            {
                "year": year,
                "available_years": available_years,
                "invoices": invoices,
                "total_income": total_income,
                "monthly_breakdown": monthly_breakdown,
                "kleinunternehmer_limit": limit,
                "kleinunternehmer_ok": total_income <= limit,
                "kleinunternehmer_warning": total_income >= limit * Decimal("0.8"),
                "kleinunternehmer_remaining": remaining,
                "is_premium": is_premium,
                "total_expenses": total_expenses,
                "profit": total_profit,
                "total_profit": total_profit,
                "expenses_by_category": expenses_by_category,
                "expense_list": expenses_qs,
            }
        )
        return context


class TaxYearCsvView(LoginRequiredMixin, View):
    """CSV export of paid invoices for a tax year (cash-basis / Zufluss-Prinzip)."""

    def get(self, request, *args, **kwargs):
        user = request.user
        now = timezone.now()
        try:
            year = int(request.GET.get("year", now.year))
        except (ValueError, TypeError):
            year = now.year

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="tutorflow-einnahmen-{year}.csv"'
        response.write("\ufeff")  # BOM for Excel UTF-8

        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                _("Date"),
                _("Invoice number"),
                _("Recipient"),
                _("Amount (EUR)"),
            ]
        )

        for inv in (
            Invoice.objects.filter(
                owner=user,
                status="paid",
                paid_at__isnull=False,
                paid_at__year=year,
            )
            .order_by("paid_at")
            .only("invoice_number", "payer_name", "paid_at", "total_amount")
        ):
            writer.writerow(
                [
                    inv.paid_at.date().strftime("%d.%m.%Y"),
                    inv.invoice_number or "",
                    inv.payer_name,
                    str(inv.total_amount).replace(".", ","),
                ]
            )

        writer.writerow([])
        writer.writerow([_("Expenses")])
        writer.writerow([_("Date"), _("Category"), _("Description"), _("Amount (EUR)")])

        category_labels = dict(Expense.CATEGORY_CHOICES)
        for exp in Expense.objects.filter(user=user, date__year=year).order_by("date"):
            writer.writerow(
                [
                    exp.date.strftime("%d.%m.%Y"),
                    str(category_labels.get(exp.category, exp.category)),
                    exp.description,
                    str(exp.amount).replace(".", ","),
                ]
            )

        return response


class ExpenseListView(LoginRequiredMixin, ListView):
    model = Expense
    template_name = "core/expense_list.html"
    context_object_name = "expenses"

    def get_queryset(self):
        qs = Expense.objects.filter(user=self.request.user)
        year = self.request.GET.get("year")
        if year:
            try:
                qs = qs.filter(date__year=int(year))
            except (ValueError, TypeError):
                pass
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        year_param = self.request.GET.get("year")
        try:
            year_filter = int(year_param) if year_param else now.year
        except (ValueError, TypeError):
            year_filter = now.year

        total_expense = Expense.objects.filter(
            user=self.request.user, date__year=year_filter
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        existing_years = list(
            Expense.objects.filter(user=self.request.user)
            .dates("date", "year")
            .values_list("date__year", flat=True)
            .order_by("-date__year")
        )
        if now.year not in existing_years:
            existing_years = sorted(set(existing_years + [now.year]), reverse=True)

        context["year_filter"] = year_filter
        context["total_expense"] = total_expense
        context["available_years"] = existing_years
        return context


class ExpenseCreateView(LoginRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "core/expense_form.html"
    success_url = reverse_lazy("core:expense_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, _("Expense saved."))
        return super().form_valid(form)


class ExpenseUpdateView(LoginRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "core/expense_form.html"
    success_url = reverse_lazy("core:expense_list")

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Expense updated."))
        return super().form_valid(form)


class ExpenseDeleteView(LoginRequiredMixin, DeleteView):
    model = Expense
    template_name = "core/expense_confirm_delete.html"
    success_url = reverse_lazy("core:expense_list")

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Expense deleted."))
        return super().form_valid(form)


class EuerView(LoginRequiredMixin, TemplateView):
    """EÜR – Einnahmenüberschussrechnung nach §4 Abs.3 EStG."""

    template_name = "core/euer.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()

        try:
            year = int(self.request.GET.get("year", now.year))
        except (ValueError, TypeError):
            year = now.year

        available_year_dates = (
            Invoice.objects.filter(owner=user, paid_at__isnull=False)
            .dates("paid_at", "year")
            .order_by("-paid_at")
        )
        available_years = [d.year for d in available_year_dates]
        if year not in available_years:
            available_years = sorted(set(available_years + [year]), reverse=True)

        total_income = Invoice.objects.filter(
            owner=user, status="paid", paid_at__isnull=False, paid_at__year=year
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

        expenses_qs = list(Expense.objects.filter(user=user, date__year=year))
        total_expenses = sum((e.effective_amount for e in expenses_qs), Decimal("0.00"))

        category_labels = dict(Expense.CATEGORY_CHOICES)
        category_sums: dict = {}
        for e in expenses_qs:
            label = category_labels.get(e.category, e.category)
            category_sums[label] = category_sums.get(label, Decimal("0.00")) + e.effective_amount
        expenses_by_category = {k: v for k, v in sorted(category_sums.items()) if v > 0}

        context.update(
            {
                "year": year,
                "available_years": available_years,
                "total_income": total_income,
                "expenses_by_category": expenses_by_category,
                "total_expenses": total_expenses,
                "profit": total_income - total_expenses,
            }
        )
        return context

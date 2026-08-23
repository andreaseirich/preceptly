"""
Views for dashboard and income overview.
"""

import csv
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
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
    ReviewForm,
    TravelPolicyForm,
    UserEmailForm,
    WorkingHoursForm,
)
from apps.core.models import Expense, Review, UserProfile
from apps.core.selectors import IncomeSelector
from apps.lessons.services import LessonConflictService, SessionQueryService
from apps.lessons.status_service import SessionStatusUpdater

logger = logging.getLogger(__name__)

LEGAL_LAST_UPDATED = "08.04.2026"


class LandingPageView(TemplateView):
    """Landing page -- redirects authenticated users to dashboard."""

    template_name = "core/landing.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from django.db.models import Avg, Count

        context = super().get_context_data(**kwargs)
        approved = list(
            Review.objects.filter(is_approved=True).exclude(comment="").select_related("user")[:6]
        )
        for review in approved:
            review.stars_display = "\u2605" * review.rating + "\u2606" * (5 - review.rating)
        stats = Review.objects.filter(is_approved=True).aggregate(
            avg=Avg("rating"), count=Count("id")
        )
        context["approved_reviews"] = approved
        context["review_average"] = stats["avg"]
        context["review_count"] = stats["count"]
        return context


class SubmitReviewView(LoginRequiredMixin, View):
    """Tutor submits (or updates) their star rating + optional feedback.

    Not shown publicly until an admin sets is_approved=True in Django admin.
    """

    def post(self, request, *args, **kwargs):
        try:
            review = Review.objects.get(user=request.user)
        except Review.DoesNotExist:
            review = Review(user=request.user)
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(
                request, _("Thanks for your feedback! It'll appear publicly once reviewed.")
            )
        else:
            messages.error(request, _("Please select a rating between 1 and 5 stars."))
        return redirect("core:dashboard")


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
        try:
            year = max(2000, min(int(self.request.GET.get("year", now.year)), 2100))
        except (ValueError, TypeError):
            year = now.year
        if "month" in self.request.GET:
            try:
                month = max(1, min(int(self.request.GET.get("month")), 12))
            except (ValueError, TypeError):
                month = now.month
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


# TODO: Add rate limiting on POST (install django_ratelimit, then:
# @method_decorator(ratelimit(key="user", rate="20/m", method="POST", block=False), name="post")
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
            if request.user.email:
                # Changing an existing email is blocked in the UI (security
                # hardening, see commit 077c4af): only first-time addition is
                # self-service, to limit account-takeover / billing-hijack risk.
                messages.info(
                    request,
                    _("To change your email address, please contact support."),
                )
                return redirect(self.success_url)
            email_form = UserEmailForm(request.POST, instance=request.user)
            if email_form.is_valid():
                email_form.save()
                messages.success(request, _("Email address saved."))
                return redirect(self.success_url)
            context = self.get_context_data()
            context["email_form"] = email_form
            return self.render_to_response(context)
        if "save_travel" in request.POST:
            travel_form = TravelPolicyForm(request.POST)
            if travel_form.is_valid():
                profile, _created = UserProfile.objects.get_or_create(user=request.user)
                policy = dict(profile.travel_policy or {})
                policy["transport_mode"] = travel_form.cleaned_data["transport_mode"]
                buffer = travel_form.cleaned_data.get("fahrrad_buffer_minutes")
                policy["fahrrad_buffer_minutes"] = buffer if buffer is not None else 25
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
        if "save_timezone" in request.POST:
            tz_value = request.POST.get("timezone", "Europe/Berlin").strip()
            import zoneinfo

            try:
                zoneinfo.ZoneInfo(tz_value)  # Validierung
                profile, _created = UserProfile.objects.get_or_create(user=request.user)
                profile.timezone = tz_value
                profile.save(update_fields=["timezone"])
                messages.success(request, _("Timezone saved."))
            except (KeyError, zoneinfo.ZoneInfoNotFoundError):
                messages.error(request, _("Invalid timezone."))
            return redirect(self.success_url)
        if "save_billing_profile" in request.POST:
            from apps.core.validators import validate_billing_tax_number

            tax_raw = request.POST.get("billing_tax_number", "").strip()[:50]
            tax_error = validate_billing_tax_number(tax_raw) if tax_raw else None
            if tax_error:
                messages.error(request, tax_error)
                return redirect(self.success_url)
            profile, _created = UserProfile.objects.get_or_create(user=request.user)
            profile.billing_name = request.POST.get("billing_name", "").strip()[:200]
            profile.billing_address = request.POST.get("billing_address", "").strip()[:2000]
            profile.billing_tax_number = tax_raw
            profile.billing_email = request.POST.get("billing_email", "").strip()[:254]
            profile.billing_phone = request.POST.get("billing_phone", "").strip()[:30]
            profile.billing_website = request.POST.get("billing_website", "").strip()[:200]
            profile.billing_bank_iban = request.POST.get("billing_bank_iban", "").strip()[:34]
            profile.billing_bank_bic = request.POST.get("billing_bank_bic", "").strip()[:11]
            profile.billing_kleinunternehmer = "billing_kleinunternehmer" in request.POST
            profile.save()
            messages.success(request, _("Rechnungsdaten gespeichert."))
            return redirect(self.success_url)
        if "save_notifications" in request.POST:
            from apps.core.models import NotificationPreference

            notif_pref, _created = NotificationPreference.objects.get_or_create(user=request.user)
            notif_pref.notify_portal_booking_email = bool(
                request.POST.get("notify_portal_booking_email")
            )
            notif_pref.notify_portal_booking_push = bool(
                request.POST.get("notify_portal_booking_push")
            )
            notif_pref.save(
                update_fields=[
                    "notify_portal_booking_email",
                    "notify_portal_booking_push",
                    "updated_at",
                ]
            )
            messages.success(request, _("Notification settings saved."))
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add profile, contracts, and booking links to context."""
        from django.conf import settings

        from apps.contracts.models import Contract
        from apps.core.feature_flags import is_premium_user
        from apps.core.stripe_utils import _is_valid_email_for_stripe

        context = super().get_context_data(**kwargs)
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)

        context["is_premium"] = is_premium_user(self.request.user)
        context["is_demo_user"] = self.request.user.username in ("demo_premium", "demo_user")
        context["stripe_enabled"] = getattr(settings, "STRIPE_ENABLED", False)
        context["stripe_premium_checkout_enabled"] = getattr(
            settings, "STRIPE_PREMIUM_CHECKOUT_ENABLED", False
        )
        context["stripe_price_starter"] = getattr(settings, "STRIPE_PRICE_ID_STARTER", "")
        context["stripe_price_pro"] = getattr(settings, "STRIPE_PRICE_ID_PRO", "") or getattr(
            settings, "STRIPE_PRICE_ID_MONTHLY", ""
        )
        context["stripe_price_business"] = getattr(settings, "STRIPE_PRICE_ID_BUSINESS", "")
        context["trial_available"] = not profile.trial_used

        from apps.core.referrals import ensure_referral_code

        referral_code = ensure_referral_code(profile)
        context["referral_code"] = referral_code
        if referral_code:
            from django.urls import reverse

            base_url = f"{self.request.scheme}://{self.request.get_host()}"
            register_path = reverse("core:register")
            context["referral_link"] = f"{base_url}{register_path}?ref={referral_code}"
        context["referral_free_months_pending"] = profile.referral_free_months_pending

        from apps.core.models import NotificationPreference

        notif_pref, _created = NotificationPreference.objects.get_or_create(user=self.request.user)
        context["notif_pref"] = notif_pref
        context["has_push_subscription"] = self.request.user.push_subscriptions.exists()
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
        contracts = Contract.objects.filter(is_active=True, user=self.request.user).order_by(
            "last_name", "first_name"
        )
        context["profile"] = profile
        context["current_working_hours"] = profile.default_working_hours or {}
        context["contracts"] = contracts
        context["contract_booking_urls"] = [
            {
                "contract": c,
                "url": self.request.build_absolute_uri(
                    reverse("lessons:student_booking", kwargs={"token": c.booking_token})
                ),
            }
            for c in contracts
        ]
        import zoneinfo

        context["profile_timezone"] = profile.timezone or "Europe/Berlin"
        context["all_timezones"] = sorted(zoneinfo.available_timezones())
        return context


class LegalPageView(TemplateView):
    """Base view for legal pages."""

    last_updated = LEGAL_LAST_UPDATED

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["last_updated"] = self.last_updated
        return context


class LegalImprintView(LegalPageView):
    """Imprint — fetched from e-recht24 API with fallback to static template."""

    template_name = "legal/imprint.html"

    def get_context_data(self, **kwargs):
        from apps.core.erecht24_service import get_imprint

        ALLOWED_LANGS = {"de", "en"}
        context = super().get_context_data(**kwargs)
        lang = getattr(self.request, "LANGUAGE_CODE", "de")[:2]
        if lang not in ALLOWED_LANGS:
            lang = "de"
        context["erecht24_html"] = get_imprint(lang)
        return context


class LegalPrivacyView(LegalPageView):
    """Privacy policy — fetched from e-recht24 API with fallback to static template."""

    template_name = "legal/privacy.html"

    def get_context_data(self, **kwargs):
        from apps.core.erecht24_service import get_privacy_policy

        ALLOWED_LANGS = {"de", "en"}
        context = super().get_context_data(**kwargs)
        lang = getattr(self.request, "LANGUAGE_CODE", "de")[:2]
        if lang not in ALLOWED_LANGS:
            lang = "de"
        context["erecht24_html"] = get_privacy_policy(lang)
        return context


class LegalTermsView(LegalPageView):
    """Terms of service page."""

    template_name = "legal/terms.html"


class LegalAboutView(LegalPageView):
    """About page."""

    template_name = "legal/about.html"


class LegalWithdrawalView(LegalPageView):
    """Withdrawal notice page."""

    template_name = "legal/withdrawal.html"


class LegalAvvView(LegalPageView):
    """Data processing agreement (AVV/DPA) page."""

    template_name = "legal/avv.html"


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
            year = max(2000, min(int(self.request.GET.get("year", now.year)), 2100))
        except (ValueError, TypeError):
            year = now.year

        available_year_dates = (
            Invoice.objects.filter(owner=user, status="paid", paid_at__isnull=False)
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
                monthly_income[timezone.localtime(inv.paid_at).month] += inv.total_amount
        else:
            invoices = []
            total_income = Decimal("0.00")
            monthly_income = {m: Decimal("0.00") for m in range(1, 13)}

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

        active_months = sum(1 for row in monthly_breakdown if row["income"] or row["expenses"])
        average_monthly_profit = total_profit / active_months if active_months else Decimal("0.00")

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
                "kleinunternehmer_ok": total_profit <= limit,
                "kleinunternehmer_warning": total_profit >= limit * Decimal("0.8"),
                "kleinunternehmer_remaining": max(Decimal("0.00"), limit - total_profit),
                "is_premium": is_premium,
                "total_expenses": total_expenses,
                "profit": total_profit,
                "total_profit": total_profit,
                "average_monthly_profit": average_monthly_profit,
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
        response["Content-Disposition"] = f'attachment; filename="preceptly-einnahmen-{year}.csv"'
        response.write("\ufeff")  # BOM for Excel UTF-8

        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                _("Abrechnungszeitraum"),
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
            .only("invoice_number", "payer_name", "period_start", "period_end", "total_amount")
        ):
            period = (
                f"{inv.period_start.strftime('%d.%m.%Y')} – {inv.period_end.strftime('%d.%m.%Y')}"
                if inv.period_end
                else inv.period_start.strftime("%d.%m.%Y")
            )
            writer.writerow(
                [
                    period,
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
            except (ValueError, TypeError) as exc:
                logger.debug("Invalid year filter ignored: %s", exc)
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


def _euer_data(user, year: int) -> dict:
    """Compute EÜR figures for *user* and *year*. Used by EuerView and EuerPdfView."""
    available_year_dates = (
        Invoice.objects.filter(owner=user, status="paid", paid_at__isnull=False)
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

    return {
        "available_years": available_years,
        "total_income": total_income,
        "expenses_by_category": expenses_by_category,
        "total_expenses": total_expenses,
        "profit": total_income - total_expenses,
    }


class EuerView(LoginRequiredMixin, TemplateView):
    """EÜR – Einnahmenüberschussrechnung nach §4 Abs.3 EStG."""

    template_name = "core/euer.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        try:
            year = max(2000, min(int(self.request.GET.get("year", now.year)), 2100))
        except (ValueError, TypeError):
            year = now.year

        data = _euer_data(self.request.user, year)
        context.update({"year": year, **data})
        return context


class EuerPdfView(LoginRequiredMixin, View):
    """Download EÜR as a formatted PDF (reportlab)."""

    def get(self, request, *args, **kwargs):
        from apps.core.pdf_service import generate_euer_pdf

        now = timezone.now()
        try:
            year = max(2000, min(int(request.GET.get("year", now.year)), 2100))
        except (ValueError, TypeError):
            year = now.year

        data = _euer_data(request.user, year)
        language = getattr(request, "LANGUAGE_CODE", "de")

        pdf_bytes = generate_euer_pdf(
            user=request.user,
            year=year,
            total_income=data["total_income"],
            expenses_by_category=data["expenses_by_category"],
            total_expenses=data["total_expenses"],
            profit=data["profit"],
            language=language,
        )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="euer-{year}.pdf"'
        return response


class AcceptAvvView(LoginRequiredMixin, View):
    """One-click AVV/AGB/Datenschutz acceptance from settings page."""

    def post(self, request):
        if not request.POST.get("avv_consent"):
            messages.error(request, _("Please confirm the legal agreements to proceed."))
            return redirect(reverse("core:settings"))
        from django.utils import timezone

        profile, _created = UserProfile.objects.get_or_create(user=request.user)
        if not profile.avv_accepted_at:
            profile.avv_accepted_at = timezone.now()
            profile.save(update_fields=["avv_accepted_at"])
        messages.success(request, _("Legal agreements accepted."))
        return redirect(reverse("core:settings"))


class AutoDetectTimezoneView(LoginRequiredMixin, View):
    """Speichert die vom Browser erkannte Zeitzone still im Profil.
    Nur wenn der neue Wert sich vom gespeicherten unterscheidet."""

    def post(self, request):
        import zoneinfo

        tz_value = request.POST.get("timezone", "").strip()
        if not tz_value:
            return JsonResponse({"ok": False, "error": "missing"}, status=400)
        try:
            zoneinfo.ZoneInfo(tz_value)
        except (KeyError, zoneinfo.ZoneInfoNotFoundError):
            return JsonResponse({"ok": False, "error": "invalid"}, status=400)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.timezone != tz_value:
            profile.timezone = tz_value
            profile.save(update_fields=["timezone"])
        return JsonResponse({"ok": True, "timezone": tz_value})


class FaqView(TemplateView):
    """Public FAQ page — listed in robots.txt/sitemap.xml and shown to
    anonymous visitors in the nav, so it must not require login."""

    template_name = "core/faq.html"

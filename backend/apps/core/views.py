"""
Views for dashboard and income overview.
"""

from apps.core.forms import WorkingHoursForm
from apps.core.models import UserProfile
from apps.core.selectors import IncomeSelector
from apps.lessons.services import LessonConflictService, SessionQueryService
from apps.lessons.status_service import SessionStatusUpdater
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView


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

    def get_context_data(self, **kwargs):
        """Add profile and contracts to context."""
        context = super().get_context_data(**kwargs)
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        from apps.contracts.models import Contract

        contracts = (
            Contract.objects.filter(is_active=True, student__user=self.request.user)
            .select_related("student")
            .order_by("student__last_name", "student__first_name")
        )
        context["profile"] = profile
        context["current_working_hours"] = profile.default_working_hours or {}
        context["contracts"] = contracts
        return context

"""
Views for dashboard and income overview.
"""

from apps.core.selectors import IncomeSelector
from apps.lessons.services import LessonConflictService, LessonQueryService
from apps.lessons.status_service import LessonStatusUpdater
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard with overview of today's lessons, conflicts, and income."""

    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Automatic status update for past lessons
        LessonStatusUpdater.update_past_lessons_to_taught()

        now = timezone.now()

        # Today's lessons
        today_lessons = LessonQueryService.get_today_lessons()
        for lesson in today_lessons:
            lesson.conflicts = LessonConflictService.check_conflicts(lesson)

        # Upcoming lessons
        upcoming_lessons = LessonQueryService.get_upcoming_lessons(days=7)
        for lesson in upcoming_lessons:
            lesson.conflicts = LessonConflictService.check_conflicts(lesson)

        # Count conflicts (convert both QuerySets to lists for combination)
        all_lessons = list(today_lessons) + list(upcoming_lessons)
        conflict_count = sum(1 for lesson in all_lessons if lesson.conflicts)

        # Income for current month
        current_month_income = IncomeSelector.get_monthly_income(now.year, now.month, status="paid")

        # Income by status for current month
        income_by_status = IncomeSelector.get_income_by_status(year=now.year, month=now.month)

        # Premium status
        from apps.core.utils import is_premium_user

        context["is_premium"] = (
            is_premium_user(self.request.user) if self.request.user.is_authenticated else False
        )

        context.update(
            {
                "today_lessons": today_lessons,
                "upcoming_lessons": upcoming_lessons,
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

        # Automatic status update for past lessons
        LessonStatusUpdater.update_past_lessons_to_taught()

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

        if month:
            # Monthly view
            monthly_income = IncomeSelector.get_monthly_income(year, month, status="paid")
            income_by_status = IncomeSelector.get_income_by_status(year=year, month=month)
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
            yearly_income = IncomeSelector.get_yearly_income(year, status="paid")
            income_by_status = IncomeSelector.get_income_by_status(year=year)
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

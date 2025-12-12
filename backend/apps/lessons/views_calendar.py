"""
Calendar views for lessons (Week, Month, Calendar redirect).
"""

from datetime import timedelta

from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService, LessonQueryService
from apps.lessons.status_service import LessonStatusUpdater
from apps.lessons.week_service import WeekService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, TemplateView


class WeekView(LoginRequiredMixin, TemplateView):
    """Week view for lessons and blocked times."""

    template_name = "lessons/week.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Automatic status update for past lessons
        LessonStatusUpdater.update_past_lessons_to_taught()

        # Year, month and day from URL parameters (fallback: current date)
        year_param = self.request.GET.get("year")
        month_param = self.request.GET.get("month")
        day_param = self.request.GET.get("day")

        if year_param and month_param and day_param:
            year = int(year_param)
            month = int(month_param)
            day = int(day_param)
        else:
            # Fallback: current date
            now = timezone.now()
            year = now.year
            month = now.month
            day = now.day

        # Load week data
        week_data = WeekService.get_week_data(year, month, day)

        # Navigation: Previous/Next week
        week_start = week_data["week_start"]
        prev_week = week_start - timedelta(days=7)
        next_week = week_start + timedelta(days=7)

        # Create weekday list
        weekdays = []
        # Weekday names will be translated in template using i18n
        weekday_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        weekday_names_short = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for i in range(7):
            day_date = week_start + timedelta(days=i)
            weekdays.append(
                {
                    "date": day_date,
                    "name": weekday_names[i],
                    "name_short": weekday_names_short[i],
                    "lessons": week_data["lessons_by_date"].get(day_date, []),
                    "blocked_times": week_data["blocked_times_by_date"].get(day_date, []),
                }
            )

        # Today for template comparison
        today = timezone.localdate()

        # Hours list for template (8-22)
        hours = list(range(8, 23))

        context.update(
            {
                "week_start": week_start,
                "week_end": week_data["week_end"],
                "weekdays": weekdays,
                "conflicts_by_lesson": week_data["conflicts_by_lesson"],
                "prev_week": prev_week,
                "next_week": next_week,
                "today": today,
                "hours": hours,
            }
        )

        return context


class LessonMonthView(LoginRequiredMixin, ListView):
    """Month view of all lessons."""

    model = Lesson
    template_name = "lessons/lesson_month.html"
    context_object_name = "lessons"

    def get_queryset(self):
        """Returns lessons for the specified month."""
        year = int(self.kwargs.get("year", timezone.now().year))
        month = int(self.kwargs.get("month", timezone.now().month))
        return LessonQueryService.get_lessons_for_month(year, month)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = int(self.kwargs.get("year", timezone.now().year))
        month = int(self.kwargs.get("month", timezone.now().month))

        # Add conflict info
        for lesson in context["lessons"]:
            lesson.conflicts = LessonConflictService.check_conflicts(lesson)

        context["year"] = year
        context["month"] = month
        return context


class CalendarView(LoginRequiredMixin, TemplateView):
    """Redirect to week view - legacy calendar view."""

    def get(self, request, *args, **kwargs):
        """Redirect to week view with appropriate parameters."""
        year_param = request.GET.get("year")
        month_param = request.GET.get("month")
        day_param = request.GET.get("day")

        if year_param and month_param:
            year = int(year_param)
            month = int(month_param)
            day = int(day_param) if day_param else 1
        else:
            # Fallback to today
            now = timezone.now()
            year = now.year
            month = now.month
            day = now.day

        url = reverse("lessons:week") + f"?year={year}&month={month}&day={day}"
        return HttpResponseRedirect(url)

"""
Calendar views for lessons (Week, Month, Calendar redirect).
"""

from calendar import month_name, monthcalendar
from datetime import date, timedelta

from apps.lessons.calendar_service import CalendarService
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService, LessonQueryService
from apps.lessons.status_service import LessonStatusUpdater
from apps.lessons.week_service import WeekService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic import ListView, TemplateView


class WeekView(LoginRequiredMixin, TemplateView):
    """Week view for lessons and blocked times."""

    template_name = "lessons/week.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Automatic status update for past lessons
        LessonStatusUpdater.update_past_lessons_to_taught()

        # Store this view as the last used calendar view in session
        self.request.session["last_calendar_view"] = "week"

        # Year, month and day from URL parameters (fallback: current date)
        year_param = self.request.GET.get("year")
        month_param = self.request.GET.get("month")
        day_param = self.request.GET.get("day")
        date_param = self.request.GET.get("date")

        if date_param:
            try:
                date_obj = date.fromisoformat(date_param)
                year = date_obj.year
                month = date_obj.month
                day = date_obj.day
            except (ValueError, TypeError):
                # Fallback: current date
                now = timezone.now()
                year = now.year
                month = now.month
                day = now.day
        elif year_param and month_param and day_param:
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
        week_data = WeekService.get_week_data(year, month, day, user=self.request.user)

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
        return LessonQueryService.get_lessons_for_month(year, month, user=self.request.user)

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
    """Month calendar view with date navigation."""

    template_name = "lessons/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Automatic status update for past lessons
        LessonStatusUpdater.update_past_lessons_to_taught()

        # Store this view as the last used calendar view in session
        self.request.session["last_calendar_view"] = "calendar"

        # Year and month from URL parameters (fallback: current date)
        # Support both ?year=X&month=Y and ?date=YYYY-MM-DD
        # Initialize with current date as default
        now = timezone.now()
        year = now.year
        month = now.month

        # Try to parse date parameter
        date_param = self.request.GET.get("date")
        if date_param:
            try:
                date_obj = date.fromisoformat(date_param)
                year = date_obj.year
                month = date_obj.month
            except (ValueError, TypeError):
                # Invalid date format - keep default values
                pass

        # Override with year/month parameters if provided
        year_param = self.request.GET.get("year")
        month_param = self.request.GET.get("month")
        if year_param and month_param:
            try:
                year = int(year_param)
                month = int(month_param)
            except (ValueError, TypeError):
                # Invalid parameters - keep existing values
                pass

        # Load calendar data
        calendar_data = CalendarService.get_calendar_data(year, month, user=self.request.user)

        # Calculate previous and next month
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1

        if month == 12:
            next_year = year + 1
            next_month = 1
        else:
            next_year = year
            next_month = month + 1

        # Generate calendar weeks
        cal = monthcalendar(year, month)
        weeks = []
        today = timezone.localdate()

        for week in cal:
            week_days = []
            for day in week:
                if day == 0:
                    week_days.append(None)
                else:
                    day_date = date(year, month, day)
                    week_days.append(
                        {
                            "date": day_date,
                            "is_current_month": True,
                            "lessons": calendar_data["lessons_by_date"].get(day_date, []),
                            "blocked_times": calendar_data["blocked_times_by_date"].get(
                                day_date, []
                            ),
                        }
                    )
            weeks.append(week_days)

        # Weekday names (will be translated in template)
        weekday_names = [
            _("Monday"),
            _("Tuesday"),
            _("Wednesday"),
            _("Thursday"),
            _("Friday"),
            _("Saturday"),
            _("Sunday"),
        ]

        context.update(
            {
                "year": year,
                "month": month,
                "month_label": month_name[month],
                "weeks": weeks,
                "weekday_names": weekday_names,
                "conflicts_by_lesson": calendar_data["conflicts_by_lesson"],
                "prev_year": prev_year,
                "prev_month": prev_month,
                "next_year": next_year,
                "next_month": next_month,
                "today": today,
            }
        )

        return context

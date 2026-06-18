"""
Calendar views for lessons (Week, Month, Calendar redirect).
"""

import logging
from calendar import monthcalendar
from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic import ListView, TemplateView

from apps.lessons.calendar_service import CalendarService
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService, LessonQueryService
from apps.lessons.status_service import LessonStatusUpdater
from apps.lessons.week_service import WeekService

logger = logging.getLogger(__name__)


def get_last_calendar_url(request):
    """Returns the URL of the last visited calendar position from the session."""
    import datetime as dt_mod

    view = request.session.get("last_calendar_view", "week")
    year = request.session.get("last_calendar_year")
    month = request.session.get("last_calendar_month")
    day = request.session.get("last_calendar_day")

    now = timezone.localdate()
    y = year or now.year
    m = month or now.month
    d = day or now.day

    try:
        y, m, d = int(y), int(m), int(d)
        dt_mod.date(y, m, d)  # Plausibilitätscheck
    except (ValueError, TypeError):
        today = timezone.localdate()
        y, m, d = today.year, today.month, today.day

    if view == "calendar":
        return reverse("lessons:calendar") + f"?year={y}&month={m}"
    return reverse("lessons:week") + f"?year={y}&month={m}&day={d}"


class WeekView(LoginRequiredMixin, TemplateView):
    """Week view for lessons and blocked times."""

    template_name = "lessons/week.html"

    def get_context_data(self, **kwargs):
        import datetime as _datetime
        import re

        context = super().get_context_data(**kwargs)

        LessonStatusUpdater.update_past_lessons_to_taught()

        year_param = self.request.GET.get("year")
        month_param = self.request.GET.get("month")
        day_param = self.request.GET.get("day")
        date_param = self.request.GET.get("date")

        DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

        if date_param:
            if len(date_param) <= 10 and DATE_RE.match(date_param):
                try:
                    date_obj = date.fromisoformat(date_param)
                    year = date_obj.year
                    month = date_obj.month
                    day = date_obj.day
                except ValueError:
                    now = timezone.localdate()
                    year = now.year
                    month = now.month
                    day = now.day
            else:
                now = timezone.localdate()
                year = now.year
                month = now.month
                day = now.day
        elif year_param and month_param and day_param:
            try:
                year = int(year_param)
                month = int(month_param)
                day = int(day_param)
                _datetime.date(year, month, day)  # Plausibilitätscheck
            except (ValueError, TypeError):
                today = timezone.localdate()
                year, month, day = today.year, today.month, today.day
        else:
            now = timezone.localdate()
            year = now.year
            month = now.month
            day = now.day

        self.request.session["last_calendar_view"] = "week"
        self.request.session["last_calendar_year"] = year
        self.request.session["last_calendar_month"] = month
        self.request.session["last_calendar_day"] = day

        week_data = WeekService.get_week_data(year, month, day, user=self.request.user)

        week_start = week_data["week_start"]
        prev_week = week_start - timedelta(days=7)
        next_week = week_start + timedelta(days=7)

        weekdays = []
        weekday_names = [
            _("Monday"),
            _("Tuesday"),
            _("Wednesday"),
            _("Thursday"),
            _("Friday"),
            _("Saturday"),
            _("Sunday"),
        ]
        weekday_names_short = [
            _("Mon"),
            _("Tue"),
            _("Wed"),
            _("Thu"),
            _("Fri"),
            _("Sat"),
            _("Sun"),
        ]

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

        today = timezone.localdate()
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
        now = timezone.now()
        try:
            year = int(self.kwargs.get("year", now.year))
            month = int(self.kwargs.get("month", now.month))
            import datetime as _datetime

            _datetime.date(year, month, 1)  # Plausibilitätscheck
        except (ValueError, TypeError):
            year = now.year
            month = now.month
        return LessonQueryService.get_lessons_for_month(year, month, user=self.request.user)

    def get_context_data(self, **kwargs):
        import datetime as _datetime

        context = super().get_context_data(**kwargs)
        now = timezone.now()
        try:
            year = int(self.kwargs.get("year", now.year))
            month = int(self.kwargs.get("month", now.month))
            _datetime.date(year, month, 1)  # Plausibilitätscheck
        except (ValueError, TypeError):
            year = now.year
            month = now.month

        for lesson in context["lessons"]:
            lesson.conflicts = LessonConflictService.check_conflicts(lesson)

        context["year"] = year
        context["month"] = month
        return context


class CalendarView(LoginRequiredMixin, TemplateView):
    """Month calendar view with date navigation."""

    template_name = "lessons/calendar.html"

    def get_context_data(self, **kwargs):
        import datetime as _datetime
        import re

        context = super().get_context_data(**kwargs)

        LessonStatusUpdater.update_past_lessons_to_taught()

        now = timezone.now()
        year = now.year
        month = now.month

        DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

        date_param = self.request.GET.get("date")
        if date_param:
            if len(date_param) <= 10 and DATE_RE.match(date_param):
                try:
                    date_obj = date.fromisoformat(date_param)
                    year = date_obj.year
                    month = date_obj.month
                except ValueError as exc:
                    logger.debug("Invalid date param ignored: %s", exc)
            else:
                logger.debug("Invalid date param format ignored: %s", date_param)

        year_param = self.request.GET.get("year")
        month_param = self.request.GET.get("month")
        if year_param and month_param:
            try:
                year = int(year_param)
                month = int(month_param)
                _datetime.date(year, month, 1)  # Plausibilitätscheck
            except (ValueError, TypeError) as exc:
                logger.debug("Invalid year/month params ignored: %s", exc)
                year = now.year
                month = now.month

        self.request.session["last_calendar_view"] = "calendar"
        self.request.session["last_calendar_year"] = year
        self.request.session["last_calendar_month"] = month

        calendar_data = CalendarService.get_calendar_data(year, month, user=self.request.user)

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

        month_names = [
            _("January"),
            _("February"),
            _("March"),
            _("April"),
            _("May"),
            _("June"),
            _("July"),
            _("August"),
            _("September"),
            _("October"),
            _("November"),
            _("December"),
        ]
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
                "month_label": month_names[month - 1],
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

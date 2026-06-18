"""
Views for lesson plan management.
"""

import re
from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from apps.lessons.models import Lesson

_YEAR_RE = re.compile(r"^\d{4}$")
_MONTH_RE = re.compile(r"^\d{1,2}$")
_DAY_RE = re.compile(r"^\d{1,2}$")


class LessonPlanView(LoginRequiredMixin, View):
    """Redirect to lesson detail page (lesson plan is now integrated there)."""

    def get(self, request, lesson_id):
        lesson = get_object_or_404(
            Lesson,
            pk=lesson_id,
            contract__user=request.user,
        )

        year = request.GET.get("year", "")
        month = request.GET.get("month", "")
        day = request.GET.get("day", "")

        params = {}
        if year and _YEAR_RE.match(year):
            params["year"] = year
        if month and _MONTH_RE.match(month):
            params["month"] = month
        if day and _DAY_RE.match(day):
            params["day"] = day

        url = reverse("lessons:detail", args=[lesson.pk])
        if params:
            url += "?" + urlencode(params)
        return redirect(url)

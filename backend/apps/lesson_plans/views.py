"""
Views for lesson plan management.
"""

from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View


class LessonPlanView(LoginRequiredMixin, View):
    """Redirect to lesson detail page (lesson plan is now integrated there)."""

    def get(self, request, lesson_id):
        year = request.GET.get("year", "")
        month = request.GET.get("month", "")
        day = request.GET.get("day", "")
        url = reverse("lessons:detail", args=[lesson_id])
        params = {k: v for k, v in [("year", year), ("month", month), ("day", day)] if v}
        if params:
            url += "?" + urlencode(params)
        return redirect(url)

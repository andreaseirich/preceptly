"""
Views for lesson plan management.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View


class LessonPlanView(LoginRequiredMixin, View):
    """Redirect to lesson detail page (lesson plan is now integrated there)."""

    def get(self, request, lesson_id):
        year = request.GET.get("year", "")
        month = request.GET.get("month", "")
        day = request.GET.get("day", "")
        url = f"/lessons/{lesson_id}/"
        params = "&".join(
            f"{k}={v}" for k, v in [("year", year), ("month", month), ("day", day)] if v
        )
        if params:
            url += "?" + params
        return redirect(url)

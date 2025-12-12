"""
Views for lesson plan management.
"""

from apps.core.utils import is_premium_user
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView


class LessonPlanView(LoginRequiredMixin, TemplateView):
    """View for displaying and managing lesson plans for a lesson."""

    template_name = "lesson_plans/lesson_plan.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson_id = self.kwargs.get("lesson_id")
        lesson = get_object_or_404(Lesson, pk=lesson_id)

        # Get existing lesson plans for this lesson
        lesson_plans = LessonPlan.objects.filter(lesson=lesson).order_by("-created_at")
        latest_lesson_plan = lesson_plans.first() if lesson_plans.exists() else None

        # Load conflicts for this lesson
        conflicts = LessonConflictService.check_conflicts(lesson, exclude_self=True)

        # Extract conflict types for template
        conflict_lessons = []
        conflict_blocked_times = []
        quota_conflicts = []

        for conflict in conflicts:
            if conflict["type"] == "lesson":
                conflict_lessons.append(conflict["object"])
            elif conflict["type"] == "blocked_time":
                conflict_blocked_times.append(conflict["object"])
            elif conflict["type"] == "quota":
                quota_conflicts.append(conflict)

        # Premium status
        context["lesson"] = lesson
        context["lesson_plans"] = lesson_plans
        context["has_lesson_plan"] = lesson_plans.exists()
        context["latest_lesson_plan"] = latest_lesson_plan
        context["is_premium"] = (
            is_premium_user(self.request.user) if self.request.user.is_authenticated else False
        )

        # Conflicts
        context["conflicts"] = conflicts
        context["conflict_lessons"] = conflict_lessons
        context["conflict_blocked_times"] = conflict_blocked_times
        context["quota_conflicts"] = quota_conflicts
        context["has_conflicts"] = len(conflicts) > 0

        # Week view parameters for redirect
        context["year"] = self.request.GET.get("year", lesson.date.year)
        context["month"] = self.request.GET.get("month", lesson.date.month)
        context["day"] = self.request.GET.get("day", lesson.date.day)

        return context

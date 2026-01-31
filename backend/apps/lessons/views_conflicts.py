"""
Conflict views for lessons.
"""

from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView


class ConflictDetailView(LoginRequiredMixin, TemplateView):
    """Detail view for conflicts of a lesson."""

    template_name = "lessons/conflict_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson_id = self.kwargs.get("pk")
        lesson = get_object_or_404(Lesson, pk=lesson_id, contract__student__user=self.request.user)

        # Load conflicts
        conflicts = LessonConflictService.check_conflicts(lesson, exclude_self=True)

        # Extract conflict lessons
        conflict_lessons = []
        conflict_blocked_times = []
        quota_conflicts = []

        for conflict in conflicts:
            if conflict["type"] in ("lesson", "session"):
                conflict_lessons.append(conflict["object"])
            elif conflict["type"] == "blocked_time":
                conflict_blocked_times.append(conflict["object"])
            elif conflict["type"] == "quota":
                quota_conflicts.append(conflict)

        context.update(
            {
                "lesson": lesson,
                "conflicts": conflicts,
                "conflict_lessons": conflict_lessons,
                "conflict_blocked_times": conflict_blocked_times,
                "quota_conflicts": quota_conflicts,
                "has_conflicts": len(conflicts) > 0,
            }
        )

        return context

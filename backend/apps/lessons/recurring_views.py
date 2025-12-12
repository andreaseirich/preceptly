"""
Views für RecurringLesson-CRUD-Operationen.
"""

from apps.lessons.recurring_forms import RecurringLessonForm
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_service import RecurringLessonService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


class RecurringLessonListView(LoginRequiredMixin, ListView):
    """Liste aller wiederholenden Unterrichtsstunden."""

    model = RecurringLesson
    template_name = "lessons/recurringlesson_list.html"
    context_object_name = "recurring_lessons"
    paginate_by = 20


class RecurringLessonDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht einer wiederholenden Unterrichtsstunde."""

    model = RecurringLesson
    template_name = "lessons/recurringlesson_detail.html"
    context_object_name = "recurring_lesson"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Vorschau der zu erzeugenden Lessons
        preview = RecurringLessonService.preview_lessons(self.object)
        context["preview_count"] = len(preview)
        context["preview"] = preview[:10]  # Zeige nur erste 10
        return context


class RecurringLessonCreateView(LoginRequiredMixin, CreateView):
    """Neue wiederholende Unterrichtsstunde erstellen."""

    model = RecurringLesson
    form_class = RecurringLessonForm
    template_name = "lessons/recurringlesson_form.html"

    def get_initial(self):
        """Setzt initiale Werte, z. B. Contract aus Query-Parameter."""
        initial = super().get_initial()
        contract_id = self.request.GET.get("contract")
        if contract_id:
            initial["contract"] = contract_id
        return initial

    def get_success_url(self):
        """Nach Erstellen: Generiere Lessons und weiter zum Kalender."""
        recurring_lesson = self.object
        # Generiere Lessons automatisch
        result = RecurringLessonService.generate_lessons(recurring_lesson, check_conflicts=True)

        if result["created"] > 0:
            messages.success(
                self.request,
                ngettext(
                    "Recurring lesson created and {count} lesson generated.",
                    "Recurring lesson created and {count} lessons generated.",
                    result["created"],
                ).format(count=result["created"]),
            )

        if result["conflicts"]:
            conflict_count = len(result["conflicts"])
            messages.warning(
                self.request,
                ngettext(
                    "{count} lesson with conflicts detected.",
                    "{count} lessons with conflicts detected.",
                    conflict_count,
                ).format(count=conflict_count),
            )

        # Weiterleitung zum Kalender
        from django.utils import timezone

        today = timezone.localdate()
        return (
            reverse_lazy("lessons:week") + f"?year={today.year}&month={today.month}&day={today.day}"
        )

    def form_valid(self, form):
        messages.success(self.request, _("Recurring lesson successfully created."))
        return super().form_valid(form)


class RecurringLessonUpdateView(LoginRequiredMixin, UpdateView):
    """Wiederholende Unterrichtsstunde bearbeiten."""

    model = RecurringLesson
    form_class = RecurringLessonForm
    template_name = "lessons/recurringlesson_form.html"
    success_url = reverse_lazy("lessons:recurring_list")

    def form_valid(self, form):
        messages.success(self.request, _("Recurring lesson successfully updated."))
        return super().form_valid(form)


class RecurringLessonDeleteView(LoginRequiredMixin, DeleteView):
    """Wiederholende Unterrichtsstunde löschen."""

    model = RecurringLesson
    template_name = "lessons/recurringlesson_confirm_delete.html"
    success_url = reverse_lazy("lessons:recurring_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Recurring lesson successfully deleted."))
        return super().delete(request, *args, **kwargs)


@login_required
def generate_lessons_from_recurring(request, pk):
    """Generiert Lessons aus einer RecurringLesson."""
    recurring_lesson = get_object_or_404(RecurringLesson, pk=pk)

    result = RecurringLessonService.generate_lessons(recurring_lesson, check_conflicts=True)

    if result["created"] > 0:
        messages.success(
            request,
            ngettext(
                "{count} lesson successfully created.",
                "{count} lessons successfully created.",
                result["created"],
            ).format(count=result["created"]),
        )

    if result["skipped"] > 0:
        messages.info(
            request,
            ngettext(
                "{count} lesson skipped (already exists).",
                "{count} lessons skipped (already exist).",
                result["skipped"],
            ).format(count=result["skipped"]),
        )

    if result["conflicts"]:
        conflict_count = len(result["conflicts"])
        messages.warning(
            request,
            ngettext(
                "{count} lesson with conflicts detected. Please check the details.",
                "{count} lessons with conflicts detected. Please check the details.",
                conflict_count,
            ).format(count=conflict_count),
        )

    # Weiterleitung zum Kalender, falls Lessons erstellt wurden
    if result["created"] > 0:
        from django.urls import reverse
        from django.utils import timezone

        today = timezone.localdate()
        calendar_url = (
            reverse("lessons:week") + f"?year={today.year}&month={today.month}&day={today.day}"
        )
        return redirect(calendar_url)

    return redirect("lessons:recurring_detail", pk=pk)

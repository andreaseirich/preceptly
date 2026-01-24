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
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)


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


class RecurringLessonBulkEditView(LoginRequiredMixin, TemplateView):
    """Bulk-Edit-Ansicht für mehrere Serientermine."""

    template_name = "lessons/recurringlesson_bulk_edit.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recurring_lessons"] = RecurringLesson.objects.all().order_by(
            "contract__student", "start_date"
        )
        return context

    def post(self, request, *args, **kwargs):
        """Verarbeitet Bulk-Edit-Aktionen."""
        recurring_ids = request.POST.getlist("recurring_ids")
        action = request.POST.get("action")

        if not recurring_ids:
            messages.error(request, _("Please select at least one recurring lesson."))
            return redirect("lessons:recurring_bulk_edit")

        recurring_lessons = RecurringLesson.objects.filter(pk__in=recurring_ids)

        if action == "delete":
            count = recurring_lessons.count()
            recurring_lessons.delete()
            messages.success(
                request,
                ngettext(
                    "{count} recurring lesson successfully deleted.",
                    "{count} recurring lessons successfully deleted.",
                    count,
                ).format(count=count),
            )
        elif action == "activate":
            count = recurring_lessons.update(is_active=True)
            messages.success(
                request,
                ngettext(
                    "{count} recurring lesson activated.",
                    "{count} recurring lessons activated.",
                    count,
                ).format(count=count),
            )
        elif action == "deactivate":
            count = recurring_lessons.update(is_active=False)
            messages.success(
                request,
                ngettext(
                    "{count} recurring lesson deactivated.",
                    "{count} recurring lessons deactivated.",
                    count,
                ).format(count=count),
            )
        elif action == "update_dates":
            new_start_date = request.POST.get("new_start_date")
            new_end_date = request.POST.get("new_end_date") or None

            if not new_start_date:
                messages.error(request, _("Please provide a new start date."))
                return redirect("lessons:recurring_bulk_edit")

            from datetime import datetime

            try:
                start_date_obj = datetime.strptime(new_start_date, "%Y-%m-%d").date()
                end_date_obj = None
                if new_end_date:
                    end_date_obj = datetime.strptime(new_end_date, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, _("Invalid date format."))
                return redirect("lessons:recurring_bulk_edit")

            count = 0
            for recurring in recurring_lessons:
                recurring.start_date = start_date_obj
                if new_end_date:
                    recurring.end_date = end_date_obj
                recurring.save()
                count += 1

            messages.success(
                request,
                ngettext(
                    "{count} recurring lesson updated.",
                    "{count} recurring lessons updated.",
                    count,
                ).format(count=count),
            )
        else:
            messages.error(request, _("Invalid action."))
            return redirect("lessons:recurring_bulk_edit")

        return redirect("lessons:recurring_list")

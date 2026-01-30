"""
Views für RecurringBlockedTime-CRUD-Operationen.
"""

from apps.blocked_times.recurring_forms import RecurringBlockedTimeForm
from apps.blocked_times.recurring_models import RecurringBlockedTime
from apps.blocked_times.recurring_service import RecurringBlockedTimeService
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView


class RecurringBlockedTimeDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht einer wiederholenden Blockzeit."""

    model = RecurringBlockedTime
    template_name = "blocked_times/recurring_blockedtime_detail.html"
    context_object_name = "recurring_blocked_time"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Vorschau der zu erzeugenden BlockedTime-Einträge
        preview = RecurringBlockedTimeService.preview_blocked_times(self.object)
        context["preview"] = preview
        return context


class RecurringBlockedTimeCreateView(LoginRequiredMixin, CreateView):
    """Neue wiederholende Blockzeit erstellen."""

    model = RecurringBlockedTime
    form_class = RecurringBlockedTimeForm
    template_name = "blocked_times/recurring_blockedtime_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, _("Recurring blocked time successfully created."))
        return super().form_valid(form)

    def get_success_url(self):
        """Weiterleitung zurück zum Kalender."""
        from django.utils import timezone

        now = timezone.now()
        return reverse_lazy("lessons:week") + f"?year={now.year}&month={now.month}&day={now.day}"


class RecurringBlockedTimeUpdateView(LoginRequiredMixin, UpdateView):
    """Wiederholende Blockzeit bearbeiten."""

    model = RecurringBlockedTime
    form_class = RecurringBlockedTimeForm
    template_name = "blocked_times/recurring_blockedtime_form.html"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_success_url(self):
        """Weiterleitung zurück zum Kalender."""
        from django.utils import timezone

        now = timezone.now()
        return reverse_lazy("lessons:week") + f"?year={now.year}&month={now.month}&day={now.day}"

    def form_valid(self, form):
        messages.success(self.request, _("Recurring blocked time successfully updated."))
        return super().form_valid(form)


class RecurringBlockedTimeDeleteView(LoginRequiredMixin, DeleteView):
    """Wiederholende Blockzeit löschen."""

    model = RecurringBlockedTime
    template_name = "blocked_times/recurring_blockedtime_confirm_delete.html"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_success_url(self):
        """Weiterleitung zurück zum Kalender."""
        from django.utils import timezone

        now = timezone.now()
        return reverse_lazy("lessons:week") + f"?year={now.year}&month={now.month}&day={now.day}"

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Recurring blocked time successfully deleted."))
        return super().delete(request, *args, **kwargs)


class RecurringBlockedTimeGenerateView(LoginRequiredMixin, DetailView):
    """Generiert BlockedTime-Einträge aus einer RecurringBlockedTime."""

    model = RecurringBlockedTime
    template_name = "blocked_times/recurring_blockedtime_generate.html"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        recurring_blocked_time = self.get_object()
        check_conflicts = request.POST.get("check_conflicts", "on") == "on"

        result = RecurringBlockedTimeService.generate_blocked_times(
            recurring_blocked_time, check_conflicts=check_conflicts, dry_run=False
        )

        if result["conflicts"]:
            messages.warning(
                request,
                ngettext(
                    "{created} blocked time created, {skipped} skipped, {conflicts} conflict detected!",
                    "{created} blocked times created, {skipped} skipped, {conflicts} conflicts detected!",
                    result["created"],
                ).format(
                    created=result["created"],
                    skipped=result["skipped"],
                    conflicts=len(result["conflicts"]),
                ),
            )
        else:
            messages.success(
                request,
                ngettext(
                    "{created} blocked time successfully created, {skipped} skipped.",
                    "{created} blocked times successfully created, {skipped} skipped.",
                    result["created"],
                ).format(created=result["created"], skipped=result["skipped"]),
            )

        return redirect("blocked_times:recurring_detail", pk=recurring_blocked_time.pk)

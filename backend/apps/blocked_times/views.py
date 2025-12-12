"""
Views für BlockedTime-CRUD-Operationen.
"""

from apps.blocked_times.forms import BlockedTimeForm
from apps.blocked_times.models import BlockedTime
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView


class BlockedTimeDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht einer Blockzeit."""

    model = BlockedTime
    template_name = "blocked_times/blockedtime_detail.html"
    context_object_name = "blocked_time"


class BlockedTimeCreateView(LoginRequiredMixin, CreateView):
    """Neue Blockzeit erstellen."""

    model = BlockedTime
    form_class = BlockedTimeForm
    template_name = "blocked_times/blockedtime_form.html"

    def get_initial(self):
        """Setzt initiale Werte, z. B. Datum und Zeiten aus Query-Parametern."""
        initial = super().get_initial()

        # Unterstützung für start/end aus Drag-to-Create
        start_param = self.request.GET.get("start")
        end_param = self.request.GET.get("end")

        if start_param and end_param:
            try:
                from datetime import datetime

                from django.utils import timezone

                start_dt = datetime.fromisoformat(start_param.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_param.replace("Z", "+00:00"))

                # Konvertiere zu timezone-aware, falls nötig
                if timezone.is_naive(start_dt):
                    start_dt = timezone.make_aware(start_dt)
                if timezone.is_naive(end_dt):
                    end_dt = timezone.make_aware(end_dt)

                initial["start_datetime"] = start_dt
                initial["end_datetime"] = end_dt

                return initial
            except (ValueError, TypeError):
                # Silently ignore invalid datetime format in GET parameter
                # Form validation will catch this when user submits
                pass

        # Fallback: Normale Datum-Parameter
        date_param = self.request.GET.get("date")
        if date_param:
            from datetime import datetime

            from django.utils import timezone

            try:
                parsed_date = datetime.fromisoformat(date_param).date()
                # Setze start_datetime und end_datetime auf den Tag
                initial["start_datetime"] = timezone.make_aware(
                    datetime.combine(parsed_date, datetime.min.time().replace(hour=9))
                )
                initial["end_datetime"] = timezone.make_aware(
                    datetime.combine(parsed_date, datetime.min.time().replace(hour=10))
                )
            except (ValueError, TypeError):
                # Silently ignore invalid date format in GET parameter
                # Form validation will catch this when user submits
                pass
        return initial

    def get_success_url(self):
        """Weiterleitung zurück zur Wochenansicht."""
        blocked_time = self.object
        year = blocked_time.start_datetime.year
        month = blocked_time.start_datetime.month
        day = blocked_time.start_datetime.day
        return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"

    def form_valid(self, form):
        from apps.lessons.services import recalculate_conflicts_for_blocked_time
        from django.utils.translation import gettext_lazy as _

        blocked_time = form.save()

        # Recalculate conflicts for affected lessons
        recalculate_conflicts_for_blocked_time(blocked_time)

        messages.success(self.request, _("Blocked time successfully created."))
        return super().form_valid(form)


class BlockedTimeUpdateView(LoginRequiredMixin, UpdateView):
    """Blockzeit bearbeiten."""

    model = BlockedTime
    form_class = BlockedTimeForm
    template_name = "blocked_times/blockedtime_form.html"

    def get_success_url(self):
        """Weiterleitung zurück zum Kalender mit Jahr/Monat."""
        blocked_time = self.object
        year = blocked_time.start_datetime.year
        month = blocked_time.start_datetime.month
        # Verwende year/month/day aus Request, falls vorhanden, sonst aus BlockedTime-Datum
        year = int(self.request.GET.get("year", year))
        month = int(self.request.GET.get("month", month))
        day = int(self.request.GET.get("day", blocked_time.start_datetime.day))
        return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"

    def form_valid(self, form):
        from apps.lessons.services import recalculate_conflicts_for_blocked_time
        from django.utils.translation import gettext_lazy as _

        blocked_time = form.save()

        # Recalculate conflicts for affected lessons
        recalculate_conflicts_for_blocked_time(blocked_time)

        messages.success(self.request, _("Blocked time successfully updated."))
        return super().form_valid(form)


class BlockedTimeDeleteView(LoginRequiredMixin, DeleteView):
    """Blockzeit löschen."""

    model = BlockedTime
    template_name = "blocked_times/blockedtime_confirm_delete.html"

    def get_success_url(self):
        """Weiterleitung zurück zur Wochenansicht."""
        blocked_time = self.object
        year = blocked_time.start_datetime.year
        month = blocked_time.start_datetime.month
        day = blocked_time.start_datetime.day
        return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"

    def delete(self, request, *args, **kwargs):
        from apps.lessons.services import recalculate_conflicts_for_blocked_time
        from django.utils.translation import gettext_lazy as _

        blocked_time = self.get_object()

        # Recalculate conflicts before deleting (so we know which lessons to update)
        recalculate_conflicts_for_blocked_time(blocked_time)

        messages.success(self.request, _("Blocked time successfully deleted."))
        return super().delete(request, *args, **kwargs)

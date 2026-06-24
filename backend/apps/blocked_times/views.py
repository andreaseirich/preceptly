"""
Views für BlockedTime-CRUD-Operationen.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from apps.blocked_times.forms import BlockedTimeForm
from apps.blocked_times.models import BlockedTime


class BlockedTimeDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht einer Blockzeit."""

    model = BlockedTime
    template_name = "blocked_times/blockedtime_detail.html"
    context_object_name = "blocked_time"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class BlockedTimeCreateView(LoginRequiredMixin, CreateView):
    """Neue Blockzeit erstellen."""

    model = BlockedTime
    form_class = BlockedTimeForm
    template_name = "blocked_times/blockedtime_form.html"

    def get_initial(self):
        """Pre-fill form with date/time from request parameters (similar to LessonCreateView)."""
        initial = super().get_initial()

        from datetime import datetime, timedelta

        from django.utils import timezone

        # Support for start/end parameters from week view (ISO datetime format: YYYY-MM-DDTHH:MM)
        start_str = self.request.GET.get("start", "")
        end_str = self.request.GET.get("end", "")

        if start_str and len(start_str) <= 32:
            try:
                if "T" in start_str:
                    # ISO datetime format – einheitlich über fromisoformat
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    if start_dt.tzinfo:
                        start_dt = timezone.make_naive(start_dt)
                else:
                    # Nur Datum angegeben
                    date_obj = datetime.strptime(start_str, "%Y-%m-%d").date()
                    start_dt = datetime.combine(date_obj, datetime.min.time().replace(hour=9))

                # Timezone-aware machen
                if timezone.is_naive(start_dt):
                    start_dt = timezone.make_aware(start_dt)

                initial["start_datetime"] = start_dt

                # end_datetime ermitteln
                if end_str and len(end_str) <= 32:
                    try:
                        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                        if end_dt.tzinfo:
                            end_dt = timezone.make_naive(end_dt)
                        if timezone.is_naive(end_dt):
                            end_dt = timezone.make_aware(end_dt)
                        initial["end_datetime"] = end_dt
                    except (ValueError, TypeError):
                        initial["end_datetime"] = start_dt + timedelta(hours=1)
                else:
                    initial["end_datetime"] = start_dt + timedelta(hours=1)

            except (ValueError, TypeError):
                pass

        # Fallback: date-Parameter (Rückwärtskompatibilität)
        if "start_datetime" not in initial:
            date_str = self.request.GET.get("date", "")
            if date_str and len(date_str) <= 10:
                try:
                    from datetime import timedelta

                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    start_dt = timezone.make_aware(
                        datetime.combine(date_obj, datetime.min.time().replace(hour=9))
                    )
                    initial["start_datetime"] = start_dt
                    initial["end_datetime"] = start_dt + timedelta(hours=1)
                except ValueError:
                    pass

        return initial

    def get_success_url(self):
        """Redirect back to last used calendar view (similar to LessonCreateView)."""
        blocked_time = self.object
        # Use year/month/day from request if available, otherwise from blocked_time date
        try:
            year = int(self.request.GET.get("year", blocked_time.start_datetime.year))
            month = int(self.request.GET.get("month", blocked_time.start_datetime.month))
            day = int(self.request.GET.get("day", blocked_time.start_datetime.day))
        except (ValueError, TypeError):
            year = blocked_time.start_datetime.year
            month = blocked_time.start_datetime.month
            day = blocked_time.start_datetime.day

        # Get last used calendar view from session (default: week)
        last_view = self.request.session.get("last_calendar_view", "week")

        if last_view == "week":
            return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
        else:
            return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"

    def form_valid(self, form):
        from django.utils import timezone
        from django.utils.translation import gettext_lazy as _
        from django.utils.translation import ngettext

        from apps.blocked_times.recurring_models import RecurringBlockedTime
        from apps.blocked_times.recurring_service import RecurringBlockedTimeService
        from apps.lessons.services import recalculate_conflicts_for_blocked_time

        # --- M1: Vergangenheitsprüfung ---
        start_datetime = form.cleaned_data.get("start_datetime")
        if start_datetime and start_datetime < timezone.now():
            form.add_error("start_datetime", _("Blocked times in the past are not allowed."))
            return self.form_invalid(form)

        # Check if a recurring blocked time should be created
        is_recurring = form.cleaned_data.get("is_recurring", False)

        if is_recurring:
            # --- L2: Maximale Wiederholungsdauer prüfen ---
            MAX_RECURRENCE_DAYS = 365
            start_date = form.cleaned_data.get("start_datetime").date() if start_datetime else None
            recurrence_end_date = form.cleaned_data.get("recurrence_end_date")

            if (
                start_date
                and recurrence_end_date
                and (recurrence_end_date - start_date).days > MAX_RECURRENCE_DAYS
            ):
                form.add_error(None, _("Recurrence period may not exceed 1 year."))
                return self.form_invalid(form)

            blocked_time = form.save(commit=False)

            # Build an in-memory RecurringBlockedTime (not saved to DB) for generation
            weekdays = form.cleaned_data.get("recurrence_weekdays", [])
            temp_rbt = RecurringBlockedTime(
                user=self.request.user,
                title=blocked_time.title,
                description=blocked_time.description or "",
                start_date=blocked_time.start_datetime.date(),
                end_date=recurrence_end_date,
                start_time=blocked_time.start_datetime.time(),
                end_time=blocked_time.end_datetime.time(),
                recurrence_type=form.cleaned_data.get("recurrence_type", "weekly"),
                is_active=True,
                monday="0" in weekdays,
                tuesday="1" in weekdays,
                wednesday="2" in weekdays,
                thursday="3" in weekdays,
                friday="4" in weekdays,
                saturday="5" in weekdays,
                sunday="6" in weekdays,
            )

            # Generate BlockedTimes directly (temp_rbt is never saved to DB)
            result = RecurringBlockedTimeService.generate_blocked_times(
                temp_rbt, check_conflicts=True
            )
            recurring_blocked_time = temp_rbt  # alias for message context below

            if result["created"] > 0:
                messages.success(
                    self.request,
                    ngettext(
                        "Recurring blocked time series created and {count} blocked time generated.",
                        "Recurring blocked time series created and {count} blocked times generated.",
                        result["created"],
                    ).format(count=result["created"]),
                )
            else:
                messages.info(
                    self.request,
                    _(
                        "Recurring blocked time series created, but no new blocked times were generated (they may already exist)."
                    ),
                )

            if result["conflicts"]:
                conflict_count = len(result["conflicts"])
                messages.warning(
                    self.request,
                    ngettext(
                        "{count} blocked time with conflicts detected.",
                        "{count} blocked times with conflicts detected.",
                        conflict_count,
                    ).format(count=conflict_count),
                )

            # Set self.object for redirection
            if result.get("created", 0) > 0:
                first_blocked_time = (
                    BlockedTime.objects.filter(
                        user=self.request.user,
                        title=recurring_blocked_time.title,
                        start_datetime__date__gte=recurring_blocked_time.start_date,
                        start_datetime__time=recurring_blocked_time.start_time,
                    )
                    .order_by("start_datetime")
                    .first()
                )
                self.object = first_blocked_time
            else:
                blocked_time.user = self.request.user
                blocked_time.save()
                recalculate_conflicts_for_blocked_time(blocked_time)
                self.object = blocked_time
        else:
            # Create normal single BlockedTime
            blocked_time = form.save(commit=False)
            blocked_time.user = self.request.user
            blocked_time.save()

            # Recalculate conflicts for affected lessons
            recalculate_conflicts_for_blocked_time(blocked_time)

            conflicts = []
            from apps.lessons.models import Lesson
            from apps.lessons.services import LessonConflictService

            conflicting_lessons = Lesson.objects.filter(
                date=blocked_time.start_datetime.date(),
                contract__user=self.request.user,
            ).select_related("contract")

            for lesson in conflicting_lessons:
                lesson_start, lesson_end = LessonConflictService.calculate_time_block(lesson)
                if not (
                    blocked_time.end_datetime <= lesson_start
                    or blocked_time.start_datetime >= lesson_end
                ):
                    conflicts.append(lesson)

            if conflicts:
                messages.warning(
                    self.request,
                    _("Blocked time created, but {count} conflict(s) detected!").format(
                        count=len(conflicts)
                    ),
                )
            else:
                messages.success(self.request, _("Blocked time successfully created."))

        return super().form_valid(form)


class BlockedTimeUpdateView(LoginRequiredMixin, UpdateView):
    """Blockzeit bearbeiten."""

    model = BlockedTime
    form_class = BlockedTimeForm
    template_name = "blocked_times/blockedtime_form.html"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["matching_recurring"] = None
        return context

    def get_success_url(self):
        """Redirect back to last used calendar view (similar to LessonUpdateView)."""
        blocked_time = self.object
        # Use year/month/day from request if available, otherwise from blocked_time date
        try:
            year = int(self.request.GET.get("year", blocked_time.start_datetime.year))
            month = int(self.request.GET.get("month", blocked_time.start_datetime.month))
            day = int(self.request.GET.get("day", blocked_time.start_datetime.day))
        except (ValueError, TypeError):
            year = blocked_time.start_datetime.year
            month = blocked_time.start_datetime.month
            day = blocked_time.start_datetime.day

        # Get last used calendar view from session (default: week)
        last_view = self.request.session.get("last_calendar_view", "week")

        if last_view == "week":
            return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
        else:
            return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"

    def form_valid(self, form):
        from django.utils.translation import gettext_lazy as _

        from apps.lessons.services import recalculate_conflicts_for_blocked_time

        blocked_time = form.save()
        recalculate_conflicts_for_blocked_time(blocked_time)
        messages.success(self.request, _("Blocked time successfully updated."))

        return super().form_valid(form)


class BlockedTimeDeleteView(LoginRequiredMixin, DeleteView):
    """Blockzeit löschen."""

    model = BlockedTime
    template_name = "blocked_times/blockedtime_confirm_delete.html"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["matching_recurring"] = None
        return context

    def get_success_url(self):
        """Redirect back to last used calendar view (similar to LessonDeleteView)."""
        # Use year/month/day from request if available
        year = self.request.GET.get("year")
        month = self.request.GET.get("month")
        day = self.request.GET.get("day")

        # Get last used calendar view from session (default: week)
        last_view = self.request.session.get("last_calendar_view", "week")

        if year and month:
            if last_view == "week" and day:
                return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
            elif last_view == "week":
                # If no day provided, use current day
                from django.utils import timezone

                now = timezone.now()
                day = now.day
                return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
            else:
                return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"
        return reverse_lazy("lessons:week")

    def form_valid(self, form):
        from django.utils.translation import gettext_lazy as _

        from apps.lessons.services import recalculate_conflicts_for_blocked_time

        blocked_time = self.get_object()
        recalculate_conflicts_for_blocked_time(blocked_time)
        blocked_time.delete()
        messages.success(self.request, _("Blocked time successfully deleted."))
        return self.get_success_response()

    def get_success_response(self):
        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(self.get_success_url())

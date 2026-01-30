"""
Views for lesson CRUD operations.
"""

from apps.lessons.forms import LessonForm
from apps.lessons.models import Lesson
from apps.lessons.recurring_service import RecurringLessonService
from apps.lessons.services import LessonConflictService
from apps.lessons.status_service import LessonStatusService
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


class LessonListView(LoginRequiredMixin, ListView):
    """List of all lessons."""

    model = Lesson
    template_name = "lessons/lesson_list.html"
    context_object_name = "lessons"
    paginate_by = 50

    def get_queryset(self):
        """Filter lessons by user and optionally by date range."""
        queryset = super().get_queryset().filter(contract__student__user=self.request.user)

        # Filter by date range if provided
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset.order_by("-date", "-start_time")


class LessonDetailView(LoginRequiredMixin, DetailView):
    """Detail view of a lesson."""

    model = Lesson
    template_name = "lessons/lesson_detail.html"
    context_object_name = "lesson"

    def get_queryset(self):
        return super().get_queryset().filter(contract__student__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add last calendar view to context for template
        context["last_calendar_view"] = self.request.session.get("last_calendar_view", "week")
        return context


class LessonCreateView(LoginRequiredMixin, CreateView):
    """Create a new lesson."""

    model = Lesson
    form_class = LessonForm
    template_name = "lessons/lesson_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        """Redirect back to last used calendar view."""
        lesson = self.object
        # Use year/month/day from request if available, otherwise from lesson date
        year = int(self.request.GET.get("year", lesson.date.year))
        month = int(self.request.GET.get("month", lesson.date.month))
        day = int(self.request.GET.get("day", lesson.date.day))

        # Get last used calendar view from session (default: week)
        last_view = self.request.session.get("last_calendar_view", "week")

        if last_view == "week":
            return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
        else:
            return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"

    def get_initial(self):
        """Pre-fill form with date/time from request parameters."""
        initial = super().get_initial()

        # Support for start/end parameters from week view (ISO datetime format: YYYY-MM-DDTHH:MM)
        start_str = self.request.GET.get("start")
        end_str = self.request.GET.get("end")

        if start_str:
            try:
                from datetime import datetime

                # Parse ISO format: YYYY-MM-DDTHH:MM or YYYY-MM-DDTHH:MM:SS
                if "T" in start_str:
                    # ISO datetime format
                    if len(start_str) == 16:  # YYYY-MM-DDTHH:MM
                        start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
                    else:  # YYYY-MM-DDTHH:MM:SS or with timezone
                        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        if start_dt.tzinfo:
                            from django.utils import timezone

                            start_dt = timezone.make_naive(start_dt)
                    initial["date"] = start_dt.date()
                    initial["start_time"] = start_dt.time()

                    # Calculate duration from end parameter if provided
                    if end_str:
                        try:
                            if len(end_str) == 16:  # YYYY-MM-DDTHH:MM
                                end_dt = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
                            else:  # YYYY-MM-DDTHH:MM:SS or with timezone
                                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                                if end_dt.tzinfo:
                                    from django.utils import timezone

                                    end_dt = timezone.make_naive(end_dt)

                            # Calculate duration in minutes
                            duration = end_dt - start_dt
                            duration_minutes = int(duration.total_seconds() / 60)
                            if duration_minutes > 0:
                                initial["duration_minutes"] = duration_minutes
                        except (ValueError, TypeError):
                            # Invalid date/time format - skip duration calculation
                            pass
                else:
                    # Fallback: treat as date only
                    date_obj = datetime.strptime(start_str, "%Y-%m-%d").date()
                    initial["date"] = date_obj
            except (ValueError, TypeError):
                # Invalid date format - use default values
                pass

        # Fallback: Get date from request (for backward compatibility)
        if "date" not in initial:
            date_str = self.request.GET.get("date")
            if date_str:
                try:
                    from datetime import datetime

                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    initial["date"] = date_obj
                except ValueError:
                    # Invalid date format - use default values
                    pass

        # Fallback: Get time from request (for backward compatibility)
        if "start_time" not in initial:
            time_str = self.request.GET.get("time")
            if time_str:
                try:
                    from datetime import datetime

                    time_obj = datetime.strptime(time_str, "%H:%M").time()
                    initial["start_time"] = time_obj
                except ValueError:
                    # Invalid time format - use default values
                    pass

        return initial

    def form_valid(self, form):
        from apps.lessons.recurring_models import RecurringLesson
        from apps.lessons.recurring_service import RecurringLessonService
        from apps.lessons.services import recalculate_conflicts_for_affected_lessons
        from django.utils.translation import ngettext

        # Check if a recurring lesson should be created
        is_recurring = form.cleaned_data.get("is_recurring", False)

        if is_recurring:
            # Create a RecurringLesson instead of a single lesson
            lesson = form.save(commit=False)  # Don't save yet

            # Create RecurringLesson
            recurring_lesson = RecurringLesson(
                contract=lesson.contract,
                start_date=lesson.date,
                end_date=form.cleaned_data.get("recurrence_end_date"),
                start_time=lesson.start_time,
                duration_minutes=lesson.duration_minutes,
                travel_time_before_minutes=lesson.travel_time_before_minutes,
                travel_time_after_minutes=lesson.travel_time_after_minutes,
                recurrence_type=form.cleaned_data.get("recurrence_type", "weekly"),
                notes=lesson.notes,
                is_active=True,
            )

            # Set weekdays based on recurrence_weekdays
            weekdays = form.cleaned_data.get("recurrence_weekdays", [])
            recurring_lesson.monday = "0" in weekdays
            recurring_lesson.tuesday = "1" in weekdays
            recurring_lesson.wednesday = "2" in weekdays
            recurring_lesson.thursday = "3" in weekdays
            recurring_lesson.friday = "4" in weekdays
            recurring_lesson.saturday = "5" in weekdays
            recurring_lesson.sunday = "6" in weekdays

            recurring_lesson.save()

            # Generate lessons from RecurringLesson
            result = RecurringLessonService.generate_lessons(recurring_lesson, check_conflicts=True)

            if result["created"] > 0:
                messages.success(
                    self.request,
                    ngettext(
                        "Recurring lesson series created and {count} lesson generated.",
                        "Recurring lesson series created and {count} lessons generated.",
                        result["created"],
                    ).format(count=result["created"]),
                )
            else:
                messages.info(
                    self.request,
                    _(
                        "Recurring lesson series created, but no new lessons were generated (they may already exist)."
                    ),
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

            # Set self.object for redirection
            # Use the first created lesson or the first found lesson
            if result.get("created", 0) > 0:
                # Find the first created lesson
                from apps.lessons.models import Lesson

                first_lesson = (
                    Lesson.objects.filter(
                        contract=recurring_lesson.contract,
                        date__gte=recurring_lesson.start_date,
                        start_time=recurring_lesson.start_time,
                    )
                    .order_by("date")
                    .first()
                )
                self.object = first_lesson
            else:
                # If no lesson was created, use the original lesson
                lesson.save()
                LessonStatusService.update_status_for_lesson(lesson)
                self.object = lesson
        else:
            # Create normal single lesson
            lesson = form.save()

            # Automatic status setting
            LessonStatusService.update_status_for_lesson(lesson)

            # Recalculate conflicts for this lesson and affected lessons
            recalculate_conflicts_for_affected_lessons(lesson)

            conflicts = LessonConflictService.check_conflicts(lesson)
            if conflicts:
                messages.warning(
                    self.request,
                    _("Lesson created, but {count} conflict(s) detected!").format(
                        count=len(conflicts)
                    ),
                )
            else:
                messages.success(self.request, _("Lesson successfully created."))

        return super().form_valid(form)


class LessonUpdateView(LoginRequiredMixin, UpdateView):
    """Update a lesson."""

    model = Lesson
    form_class = LessonForm
    template_name = "lessons/lesson_form.html"

    def get_queryset(self):
        return super().get_queryset().filter(contract__student__user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.lessons.recurring_utils import find_matching_recurring_lesson

        # Check if this lesson belongs to a series
        matching_recurring = find_matching_recurring_lesson(self.object)
        context["matching_recurring"] = matching_recurring

        return context

    def get_success_url(self):
        """Redirect back to last used calendar view."""
        lesson = self.object
        # Use year/month/day from request if available, otherwise from lesson date
        year = int(self.request.GET.get("year", lesson.date.year))
        month = int(self.request.GET.get("month", lesson.date.month))
        day = int(self.request.GET.get("day", lesson.date.day))

        # Get last used calendar view from session (default: week)
        last_view = self.request.session.get("last_calendar_view", "week")

        if last_view == "week":
            return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
        else:
            return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"

    def form_valid(self, form):
        from apps.lessons.recurring_utils import find_matching_recurring_lesson
        from apps.lessons.services import recalculate_conflicts_for_affected_lessons

        # IMPORTANT: Get the original lesson instance from the database,
        # before we search for RecurringLesson (self.object already has the changed values)
        original_lesson = Lesson.objects.get(pk=self.object.pk)

        edit_scope = form.cleaned_data.get("edit_scope", "single")
        # IMPORTANT: Use original_lesson instead of self.object to find RecurringLesson
        matching_recurring = find_matching_recurring_lesson(original_lesson)

        if edit_scope == "series" and matching_recurring:
            # Edit the entire series (RecurringLesson)
            recurring = matching_recurring

            # IMPORTANT: Save the original start_time BEFORE we change it!
            original_start_time = recurring.start_time

            # IMPORTANT: Find all lessons of this series BEFORE we change RecurringLesson!
            # (Otherwise we won't find them anymore, as they still have the old start_time)
            from apps.lessons.recurring_utils import get_all_lessons_for_recurring

            all_lessons = get_all_lessons_for_recurring(
                recurring, original_start_time=original_start_time
            )

            # Check if weekdays have changed
            new_weekdays = form.cleaned_data.get("recurrence_weekdays", [])
            new_weekdays_set = {int(wd) for wd in new_weekdays}
            old_weekdays_set = set(recurring.get_active_weekdays())
            weekdays_changed = new_weekdays_set != old_weekdays_set

            # Update RecurringLesson with new values
            recurring.start_time = form.cleaned_data["start_time"]
            recurring.duration_minutes = form.cleaned_data["duration_minutes"]
            recurring.travel_time_before_minutes = form.cleaned_data["travel_time_before_minutes"]
            recurring.travel_time_after_minutes = form.cleaned_data["travel_time_after_minutes"]
            recurring.notes = form.cleaned_data["notes"]

            # Update weekdays
            if new_weekdays:
                recurring.monday = "0" in new_weekdays
                recurring.tuesday = "1" in new_weekdays
                recurring.wednesday = "2" in new_weekdays
                recurring.thursday = "3" in new_weekdays
                recurring.friday = "4" in new_weekdays
                recurring.saturday = "5" in new_weekdays
                recurring.sunday = "6" in new_weekdays

            recurring.save()

            if weekdays_changed:
                # If weekdays have changed:
                # 1. Delete all old lessons that no longer match the new weekdays
                # 2. Generate new lessons for the new weekdays

                deleted_count = 0
                for lesson in all_lessons:
                    # Check if this lesson matches the new weekdays
                    lesson_weekday = lesson.date.weekday()
                    if lesson_weekday not in new_weekdays_set:
                        # This lesson no longer belongs to the new weekdays -> delete
                        lesson.delete()
                        deleted_count += 1
                    else:
                        # This lesson still matches -> update
                        lesson.start_time = recurring.start_time
                        lesson.duration_minutes = recurring.duration_minutes
                        lesson.travel_time_before_minutes = recurring.travel_time_before_minutes
                        lesson.travel_time_after_minutes = recurring.travel_time_after_minutes
                        lesson.notes = recurring.notes
                        LessonStatusService.update_status_for_lesson(lesson)
                        lesson.save()
                        recalculate_conflicts_for_affected_lessons(lesson)

                # Generate new lessons for the new weekdays
                result = RecurringLessonService.generate_lessons(
                    recurring, check_conflicts=True, dry_run=False
                )
                created_count = result.get("created", 0)

                if result.get("conflicts"):
                    messages.warning(
                        self.request,
                        _("{count} conflict(s) detected in generated lessons.").format(
                            count=len(result.get("conflicts", []))
                        ),
                    )

                messages.success(
                    self.request,
                    _(
                        "Series updated. {deleted} lesson(s) deleted, {created} new lesson(s) created, {updated} lesson(s) updated."
                    ).format(
                        deleted=deleted_count,
                        created=created_count,
                        updated=len(all_lessons) - deleted_count,
                    ),
                )
            else:
                # Weekdays have not changed -> only update existing lessons
                updated_count = 0
                for lesson in all_lessons:
                    # Update this lesson with new values from RecurringLesson
                    lesson.start_time = recurring.start_time
                    lesson.duration_minutes = recurring.duration_minutes
                    lesson.travel_time_before_minutes = recurring.travel_time_before_minutes
                    lesson.travel_time_after_minutes = recurring.travel_time_after_minutes
                    lesson.notes = recurring.notes
                    LessonStatusService.update_status_for_lesson(lesson)
                    lesson.save()
                    updated_count += 1

                    # Recalculate conflicts
                    recalculate_conflicts_for_affected_lessons(lesson)

                messages.success(
                    self.request,
                    _("Series updated. {count} lesson(s) updated.").format(count=updated_count),
                )
        else:
            # Edit only this one lesson
            lesson = form.save()

            # Automatic status setting
            LessonStatusService.update_status_for_lesson(lesson)

            # Recalculate conflicts for this lesson and affected lessons
            recalculate_conflicts_for_affected_lessons(lesson)

            conflicts = LessonConflictService.check_conflicts(lesson)
            if conflicts:
                messages.warning(
                    self.request,
                    _("Lesson updated, but {count} conflict(s) detected!").format(
                        count=len(conflicts)
                    ),
                )
            else:
                messages.success(self.request, _("Lesson successfully updated."))

        return super().form_valid(form)


class LessonDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a lesson."""

    model = Lesson
    template_name = "lessons/lesson_confirm_delete.html"

    def get_queryset(self):
        return super().get_queryset().filter(contract__student__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.lessons.recurring_utils import (
            find_matching_recurring_lesson,
            get_all_lessons_for_recurring,
        )

        lesson = self.get_object()
        # Check if this lesson belongs to a series
        matching_recurring = find_matching_recurring_lesson(lesson)
        context["matching_recurring"] = matching_recurring

        if matching_recurring:
            # Find all lessons of this series
            all_lessons = get_all_lessons_for_recurring(matching_recurring)
            context["series_lessons_count"] = len(all_lessons)
            context["series_lessons"] = all_lessons

        return context

    def get_success_url(self):
        """Redirect back to last used calendar view."""
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
        return reverse_lazy("lessons:list")

    def delete(self, request, *args, **kwargs):
        from apps.lessons.models import Lesson
        from apps.lessons.recurring_utils import (
            find_matching_recurring_lesson,
        )
        from apps.lessons.services import recalculate_conflicts_for_affected_lessons
        from django.http import HttpResponseRedirect
        from django.utils.translation import ngettext

        lesson = self.get_object()
        lesson_date = lesson.date

        # Check if this lesson belongs to a series
        matching_recurring = find_matching_recurring_lesson(lesson)

        # Check if user wants to delete the entire series
        delete_series = request.POST.get("delete_series", "false") == "true"

        if delete_series and matching_recurring:
            # Delete the entire series
            # Use a simple and robust method: Find ALL lessons in the period
            # with the same contract and same start_time, regardless of pattern
            # (as lessons may have been manually edited)
            start_date = matching_recurring.start_date
            end_date = matching_recurring.end_date
            if not end_date and matching_recurring.contract.end_date:
                end_date = matching_recurring.contract.end_date

            # Find all lessons in the period with the same contract and same start_time
            # This is the safest method to find all lessons
            all_lessons_query = Lesson.objects.filter(
                contract=matching_recurring.contract,
                start_time=matching_recurring.start_time,
                date__gte=start_date,
            )
            if end_date:
                all_lessons_query = all_lessons_query.filter(date__lte=end_date)

            # Get all IDs
            all_lesson_ids = list(all_lessons_query.values_list("id", flat=True))
            deleted_count = len(all_lesson_ids)

            # Delete all lessons of the series directly via IDs (more efficient and safer)
            if all_lesson_ids:
                Lesson.objects.filter(id__in=all_lesson_ids).delete()

            # Delete the RecurringLesson
            matching_recurring.delete()

            messages.success(
                request,
                ngettext(
                    "Series deleted. {count} lesson deleted.",
                    "Series deleted. {count} lessons deleted.",
                    deleted_count,
                ).format(count=deleted_count),
            )
        else:
            # Delete only this one lesson
            lesson.delete()
            messages.success(self.request, _("Lesson successfully deleted."))

        # Recalculate conflicts for affected lessons on the same date
        # (We need to create a temporary lesson object with the date to check conflicts)
        from apps.lessons.models import Lesson

        temp_lesson = Lesson(date=lesson_date)
        recalculate_conflicts_for_affected_lessons(temp_lesson)

        return HttpResponseRedirect(self.get_success_url())
